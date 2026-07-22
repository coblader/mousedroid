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
 * ---- FIRST BRING-UP (do this with the droid up on blocks, wheels free) ----
 *   1. Send "L100 R0". LEFT wheels should spin FORWARD. If backward, swap that
 *      side's two motor leads on the BTS7960 (or swap RPWM/LPWM pins).
 *   2. Watch telemetry: driving forward, measured L should be POSITIVE. If it
 *      reads negative, swap that encoder's A/B wires (or negate in leftISR).
 *   3. Repeat for the right side. Only then tune PID and put it on the floor.
 */

#include <Wire.h>

// ===================== Pin map (Arduino Uno) =====================
// Encoders — D2 & D3 are the Uno's ONLY hardware-interrupt pins.
const uint8_t LEFT_ENC_A  = 2;    // interrupt
const uint8_t LEFT_ENC_B  = 4;
const uint8_t RIGHT_ENC_A = 3;    // interrupt
const uint8_t RIGHT_ENC_B = 7;

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
// Encoder: 6 pulses/motor-rev, counted on BOTH edges of channel A (x2),
// through the 1:30 gearbox -> 6 * 2 * 30 = 360 counts per WHEEL revolution.
// VERIFY: rotate a wheel exactly one full turn by hand and watch the count.
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

// ===================== Encoder ISRs =====================
volatile long leftCount  = 0;
volatile long rightCount = 0;

void leftISR() {   // on CHANGE of LEFT_ENC_A; compare with B for direction
  if (digitalRead(LEFT_ENC_A) == digitalRead(LEFT_ENC_B)) leftCount++;
  else                                                    leftCount--;
}
void rightISR() {
  if (digitalRead(RIGHT_ENC_A) == digitalRead(RIGHT_ENC_B)) rightCount++;
  else                                                      rightCount--;
}

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

  pinMode(LEFT_ENC_A, INPUT_PULLUP);  pinMode(LEFT_ENC_B, INPUT_PULLUP);
  pinMode(RIGHT_ENC_A, INPUT_PULLUP); pinMode(RIGHT_ENC_B, INPUT_PULLUP);

  pinMode(LEFT_RPWM, OUTPUT);  pinMode(LEFT_LPWM, OUTPUT);
  pinMode(RIGHT_RPWM, OUTPUT); pinMode(RIGHT_LPWM, OUTPUT);
  pinMode(DRIVER_EN, OUTPUT);  digitalWrite(DRIVER_EN, LOW);   // start disabled
  pinMode(LED_PIN, OUTPUT);

  stopMotors();

  attachInterrupt(digitalPinToInterrupt(LEFT_ENC_A),  leftISR,  CHANGE);
  attachInterrupt(digitalPinToInterrupt(RIGHT_ENC_A), rightISR, CHANGE);

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
    checkBattery();

    if (faulted) {
      stopMotors();
      digitalWrite(DRIVER_EN, LOW);           // hard cut
    } else {
      int outL = pid(targetL_mms, measL_mms, iTermL, prevErrL, dt);
      int outR = pid(targetR_mms, measR_mms, iTermR, prevErrR, dt);
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
