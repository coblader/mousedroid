/*
 * Mouse Droid (MSE-6) - Motor Controller Firmware
 * Target board: Arduino Uno
 *
 * Role: the real-time "reflexes". Reads the two wheel encoders, runs a
 * per-side PID velocity loop, and drives two BTS7960 H-bridges in
 * skid-steer (both LEFT motors on one driver, both RIGHT motors on the
 * other). Takes speed commands from the Jetson over USB serial.
 *
 * Safety: command-timeout failsafe (stops if the Jetson goes quiet) and a
 * LiPo low-voltage cutoff (latching stop so you can't over-discharge the 3S).
 *
 * ---- Serial protocol (115200 baud, newline-terminated) ----
 *   Command in:
 *     "L<mm/s> R<mm/s>"   e.g. "L200 R200"  -> both sides forward 200 mm/s
 *                              "L-150 R150"  -> spin in place
 *     "stop"              -> immediate stop
 *   Telemetry out (every 200 ms):
 *     "TEL L<mm/s> R<mm/s> V<volts> Y<deg/s>"   (+ " FAULT_LOWV" if latched)
 *
 * ---- ENCODERS: SINGLE-CHANNEL (see AGENT_LOG 2026-07-22) ----
 *   3 of the 4 motors' encoder A channels are dead; only the B channels work.
 *   So each side reads ONE working channel (a B output) on its interrupt pin and
 *   infers DIRECTION from the commanded PWM sign (leftDir/rightDir) instead of
 *   from quadrature. This gives wheel SPEED for the velocity loop, but not
 *   independent direction sensing. Because direction is taken from the command,
 *   the measured sign ALWAYS matches the command -> the MOTOR direction must be
 *   physically correct (there is no encoder A/B swap to fix a wrong sign).
 *
 * ---- FIRST BRING-UP (do this with the droid up on blocks, wheels free) ----
 *   1. Send "L100 R0". LEFT wheels should spin FORWARD. If backward, swap that
 *      side's two motor leads on the BTS7960 (or swap RPWM/LPWM pins).
 *   2. Watch telemetry: measured L should grow in magnitude with speed. (Sign
 *      follows the command by design, so it can't read "backwards" here.)
 *   3. Repeat for the right side. Only then tune PID and put it on the floor.
 */

#include <Wire.h>

// ===================== Pin map (Arduino Uno) =====================
// Encoders — SINGLE-CHANNEL. D2 & D3 are the Uno's ONLY hardware-interrupt pins.
// Put each side's ONE working encoder channel (a B output; A is dead on 3/4
// motors) on its interrupt pin. Direction is inferred from the commanded PWM
// sign, not quadrature (see header + AGENT_LOG 2026-07-22). D4/D7 now UNUSED.
const uint8_t LEFT_ENC  = 2;      // interrupt — left side single channel
const uint8_t RIGHT_ENC = 3;      // interrupt — right side single channel

// BTS7960 #1 (both LEFT motors wired in parallel to this driver)
const uint8_t LEFT_RPWM   = 5;    // PWM
const uint8_t LEFT_LPWM   = 6;    // PWM
// BTS7960 #2 (both RIGHT motors in parallel)
const uint8_t RIGHT_RPWM  = 9;    // PWM
const uint8_t RIGHT_LPWM  = 10;   // PWM

// Tie ALL four BTS7960 enables (R_EN + L_EN on both modules) to this pin.
const uint8_t DRIVER_EN   = 8;    // HIGH = enabled, LOW = hard coast (e-stop)

const uint8_t VBAT_PIN    = A0;   // 3S pack via resistor divider (see below)
const uint8_t LED_PIN     = 13;   // status: solid=fault, blink=low warn

// ===================== Robot / tuning constants =====================
// Encoder: 6 pulses/motor-rev, counted on BOTH edges (CHANGE) of the ONE wired
// channel (x2), through the 1:30 gearbox -> 6 * 2 * 30 = 360 counts per WHEEL rev
// (same total as counting one channel of a quadrature pair).
// VERIFY with the tools/ drivetrain test (spin under power, ~360 counts/rev).
const float COUNTS_PER_REV    = 360.0f;
const float WHEEL_DIAMETER_MM = 80.0f;    // <-- MEASURE your wheel and set this
const float WHEEL_CIRC_MM     = WHEEL_DIAMETER_MM * 3.14159265f;

const float MAX_SPEED_MMS     = 600.0f;   // clamp on commanded speed

// PID (per side). Start here, then tune (see notes with the sketch).
float Kp = 0.35f, Ki = 1.20f, Kd = 0.004f;

const uint16_t PID_INTERVAL_MS   = 20;    // 50 Hz control loop
const uint16_t TELEM_INTERVAL_MS = 200;
const uint16_t CMD_TIMEOUT_MS    = 500;   // no command for this long -> stop

// LiPo protection (3S). Divider ratio = (R1 + R2) / R2.
// Example: R1 = 10k (to V+), R2 = 3.3k (to GND) -> 13.3/3.3 = 4.03.
const float VOLTAGE_DIVIDER_RATIO = 4.03f;
const float ADC_REF_V   = 5.0f;
const float LOW_V_CUTOFF = 9.9f;          // 3.30 V/cell -> latch stop
const float LOW_V_WARN   = 10.5f;         // 3.50 V/cell -> blink warning
const bool  IMU_ENABLED  = false;         // set false if no MPU6050 wired
                                          // (off until drivetrain is solid;
                                          //  MPU not wired + not yet in control loop)
// LiPo low-voltage cutoff. Requires the A0 divider (R1 10k / R2 3.3k) wired.
// FALSE for bench testing on the DC adapter (no pack to protect, A0 unwired -
// would otherwise latch a false FAULT_LOWV and kill the motors).
// !!! SET TRUE when running on the LiPo (and wire the A0 divider) - over-
// discharge protection is mandatory for a 3S pack. !!!
const bool  BATTERY_MONITOR_ENABLED = false;

// ===================== Encoder ISRs (single-channel) =====================
// Count every edge of the one wired channel; direction comes from the last
// commanded PWM sign (leftDir/rightDir), set in the control loop below.
volatile long leftCount  = 0;
volatile long rightCount = 0;
volatile int8_t leftDir  = 1;     // +1 forward / -1 reverse (from commanded PWM)
volatile int8_t rightDir = 1;

void leftISR()  { leftCount  += leftDir;  }
void rightISR() { rightCount += rightDir; }

// ===================== State =====================
float targetL_mms = 0, targetR_mms = 0;
float iTermL = 0, iTermR = 0, prevErrL = 0, prevErrR = 0;
long  prevLeftCount = 0, prevRightCount = 0;
float measL_mms = 0, measR_mms = 0;
float yawRate = 0;

bool     faulted = false;      // latched on sustained low voltage
uint8_t  lowVCount = 0;
uint32_t lastCmdMs = 0, lastPidMs = 0, lastTelemMs = 0;

char lineBuf[48];
uint8_t lineLen = 0;

float gyroZbias = 0;
const uint8_t MPU_ADDR = 0x68;

// ===================== Setup =====================
void setup() {
  Serial.begin(115200);

  pinMode(LEFT_ENC, INPUT_PULLUP);
  pinMode(RIGHT_ENC, INPUT_PULLUP);

  pinMode(LEFT_RPWM, OUTPUT);  pinMode(LEFT_LPWM, OUTPUT);
  pinMode(RIGHT_RPWM, OUTPUT); pinMode(RIGHT_LPWM, OUTPUT);
  pinMode(DRIVER_EN, OUTPUT);  digitalWrite(DRIVER_EN, LOW);   // start disabled
  pinMode(LED_PIN, OUTPUT);

  stopMotors();

  attachInterrupt(digitalPinToInterrupt(LEFT_ENC),  leftISR,  CHANGE);
  attachInterrupt(digitalPinToInterrupt(RIGHT_ENC), rightISR, CHANGE);

  if (IMU_ENABLED) imuInit();     // robot must be still during startup

  digitalWrite(DRIVER_EN, HIGH);  // enable drivers
  lastCmdMs = millis();
  Serial.println(F("# mouse-droid controller ready"));
}

// ===================== Main loop =====================
void loop() {
  readSerial();
  uint32_t now = millis();

  if (now - lastPidMs >= PID_INTERVAL_MS) {
    float dt = (now - lastPidMs) / 1000.0f;
    lastPidMs = now;

    noInterrupts();
    long lc = leftCount, rc = rightCount;
    interrupts();

    long dL = lc - prevLeftCount;   prevLeftCount = lc;
    long dR = rc - prevRightCount;  prevRightCount = rc;

    // counts/s -> mm/s
    measL_mms = (dL / dt) / COUNTS_PER_REV * WHEEL_CIRC_MM;
    measR_mms = (dR / dt) / COUNTS_PER_REV * WHEEL_CIRC_MM;

    if (now - lastCmdMs > CMD_TIMEOUT_MS) { targetL_mms = 0; targetR_mms = 0; }

    if (IMU_ENABLED) yawRate = imuReadYawRate();
    if (BATTERY_MONITOR_ENABLED) checkBattery();

    if (faulted) {
      stopMotors();
      digitalWrite(DRIVER_EN, LOW);           // hard cut
    } else {
      int outL = pid(targetL_mms, measL_mms, iTermL, prevErrL, dt);
      int outR = pid(targetR_mms, measR_mms, iTermR, prevErrR, dt);
      // single-channel encoders: infer count direction from the applied PWM sign
      if (outL > 0) leftDir  = 1; else if (outL < 0) leftDir  = -1;
      if (outR > 0) rightDir = 1; else if (outR < 0) rightDir = -1;
      driveSide(LEFT_RPWM,  LEFT_LPWM,  outL);
      driveSide(RIGHT_RPWM, RIGHT_LPWM, outR);
    }
  }

  if (now - lastTelemMs >= TELEM_INTERVAL_MS) {
    lastTelemMs = now;
    Serial.print(F("TEL L")); Serial.print(measL_mms, 0);
    Serial.print(F(" R"));    Serial.print(measR_mms, 0);
    Serial.print(F(" V"));    Serial.print(readBatteryV(), 2);
    Serial.print(F(" Y"));    Serial.print(yawRate, 1);
    if (faulted) Serial.print(F(" FAULT_LOWV"));
    Serial.println();
  }
}

// ===================== PID =====================
// error in mm/s -> output PWM in [-255, 255]. Anti-windup on the I term.
int pid(float target, float meas, float &iTerm, float &prevErr, float dt) {
  if (target == 0 && fabs(meas) < 5.0f) {       // at rest: reset & coast
    iTerm = 0; prevErr = 0; return 0;
  }
  float err   = target - meas;
  iTerm      += Ki * err * dt;
  iTerm       = constrain(iTerm, -255.0f, 255.0f);
  float dTerm = Kd * (err - prevErr) / dt;
  prevErr     = err;
  float out   = Kp * err + iTerm + dTerm;
  return (int)constrain(out, -255.0f, 255.0f);
}

// BTS7960: forward = PWM on RPWM (LPWM 0); reverse = PWM on LPWM (RPWM 0)
void driveSide(uint8_t rpwm, uint8_t lpwm, int out) {
  if (out >= 0) { analogWrite(rpwm, out);  analogWrite(lpwm, 0); }
  else          { analogWrite(rpwm, 0);    analogWrite(lpwm, -out); }
}

void stopMotors() {
  analogWrite(LEFT_RPWM, 0);  analogWrite(LEFT_LPWM, 0);
  analogWrite(RIGHT_RPWM, 0); analogWrite(RIGHT_LPWM, 0);
  iTermL = iTermR = 0;
}

// ===================== Battery =====================
float readBatteryV() {
  int raw = analogRead(VBAT_PIN);
  return (raw / 1023.0f) * ADC_REF_V * VOLTAGE_DIVIDER_RATIO;
}
void checkBattery() {
  float v = readBatteryV();
  if (v < LOW_V_CUTOFF) { if (++lowVCount > 25) faulted = true; }  // ~0.5 s sustained
  else                    lowVCount = 0;
  if (faulted)              digitalWrite(LED_PIN, HIGH);
  else if (v < LOW_V_WARN)  digitalWrite(LED_PIN, (millis() / 250) & 1);
  else                      digitalWrite(LED_PIN, LOW);
}

// ===================== Serial =====================
void readSerial() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (lineLen > 0) { lineBuf[lineLen] = '\0'; parseLine(lineBuf); lineLen = 0; }
    } else if (lineLen < sizeof(lineBuf) - 1) {
      lineBuf[lineLen++] = c;
    }
  }
}
void parseLine(char *s) {
  if (strncasecmp(s, "stop", 4) == 0) {
    targetL_mms = 0; targetR_mms = 0; lastCmdMs = millis();
    return;
  }
  float l = targetL_mms, r = targetR_mms;
  bool got = false;
  for (char *p = s; *p; p++) {
    if      (*p == 'L' || *p == 'l') { l = atof(p + 1); got = true; }
    else if (*p == 'R' || *p == 'r') { r = atof(p + 1); got = true; }
  }
  if (got) {
    targetL_mms = constrain(l, -MAX_SPEED_MMS, MAX_SPEED_MMS);
    targetR_mms = constrain(r, -MAX_SPEED_MMS, MAX_SPEED_MMS);
    lastCmdMs = millis();
  }
}

// ===================== MPU6050 (optional) =====================
int16_t rawGyroZ() {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x47);                              // GYRO_ZOUT_H
  Wire.endTransmission(false);
  Wire.requestFrom((uint8_t)MPU_ADDR, (uint8_t)2);
  if (Wire.available() < 2) return 0;
  return (int16_t)((Wire.read() << 8) | Wire.read());
}
void imuInit() {
  Wire.begin();
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x6B); Wire.write(0x00);            // PWR_MGMT_1: wake up
  Wire.endTransmission(true);
  delay(50);
  long sum = 0;                                  // zero-rate bias (keep still!)
  for (int i = 0; i < 200; i++) { sum += rawGyroZ(); delay(3); }
  gyroZbias = sum / 200.0f;
}
float imuReadYawRate() {                          // deg/s, +/-250 dps -> 131 LSB/dps
  return (rawGyroZ() - gyroZbias) / 131.0f;
}
