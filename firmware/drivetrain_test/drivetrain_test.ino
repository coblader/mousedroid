/*
 * Mouse Droid (MSE-6) - DRIVETRAIN bench test (DIAGNOSTIC): drive + count.
 *
 * Combines the open-loop motor test and the encoder reader so you can spin a
 * side UNDER POWER and watch its encoder count climb - a far more reliable
 * encoder check than hand-backdriving the gearbox. Still open-loop (raw PWM,
 * no PID), so a non-counting encoder can't cause runaway.
 *
 * SINGLE-CHANNEL (matches the flight firmware after 2026-07-22): counts every
 * edge of the ONE wired channel on D2 (left) / D3 (right); direction is taken
 * from the commanded PWM sign, not quadrature (3/4 motors' A channels are dead).
 * The La/Lb/Ra/Rb levels are still printed for diagnostics (D4/D7 now unused,
 * so Lb/Rb just float high).
 *   Encoder: 6 PPR x 2 edges (CHANGE) x 30:1 = 360 counts / wheel rev.
 *
 * Pairs with tools/motor_test.py for driving (it just prints whatever telemetry
 * comes back, so the encoder counts show up in its output).
 *
 * ---- Serial (115200 baud) ----
 *   "L<pwm> R<pwm>"  raw PWM -255..255   (e.g. "L0 R80")
 *   "stop"           both to 0
 *   "z"              zero both encoder counts
 *   Prints every 200 ms:
 *     "L<pwm> R<pwm> | EL<count> ER<count>"
 */

// Motors
const uint8_t LEFT_RPWM  = 5,  LEFT_LPWM  = 6;
const uint8_t RIGHT_RPWM = 9,  RIGHT_LPWM = 10;
const uint8_t DRIVER_EN  = 8;
// Encoders
const uint8_t LEFT_ENC_A  = 2, LEFT_ENC_B  = 4;   // D2 interrupt
const uint8_t RIGHT_ENC_A = 3, RIGHT_ENC_B = 7;   // D3 interrupt

volatile long leftCount = 0, rightCount = 0;
volatile int8_t leftDir = 1, rightDir = 1;   // single-channel: dir from commanded PWM
void leftISR()  { leftCount  += leftDir;  }
void rightISR() { rightCount += rightDir; }

int outL = 0, outR = 0;
char buf[32]; uint8_t n = 0;
uint32_t lastPrint = 0;

void drive(uint8_t rp, uint8_t lp, int o) {
  o = constrain(o, -255, 255);
  if (o >= 0) { analogWrite(rp, o); analogWrite(lp, 0); }
  else        { analogWrite(rp, 0); analogWrite(lp, -o); }
}
void apply() {
  if (outL > 0) leftDir = 1; else if (outL < 0) leftDir = -1;   // dir from command
  if (outR > 0) rightDir = 1; else if (outR < 0) rightDir = -1;
  drive(LEFT_RPWM, LEFT_LPWM, outL);
  drive(RIGHT_RPWM, RIGHT_LPWM, outR);
}

void parse(char *s) {
  if (strncasecmp(s, "stop", 4) == 0) { outL = outR = 0; return; }
  for (char *p = s; *p; p++) {
    if      (*p == 'z' || *p == 'Z') { noInterrupts(); leftCount = 0; rightCount = 0; interrupts(); }
    else if (*p == 'L' || *p == 'l') outL = atoi(p + 1);
    else if (*p == 'R' || *p == 'r') outR = atoi(p + 1);
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(LEFT_RPWM, OUTPUT);  pinMode(LEFT_LPWM, OUTPUT);
  pinMode(RIGHT_RPWM, OUTPUT); pinMode(RIGHT_LPWM, OUTPUT);
  pinMode(DRIVER_EN, OUTPUT);
  pinMode(LEFT_ENC_A, INPUT_PULLUP);  pinMode(LEFT_ENC_B, INPUT_PULLUP);
  pinMode(RIGHT_ENC_A, INPUT_PULLUP); pinMode(RIGHT_ENC_B, INPUT_PULLUP);
  apply();
  digitalWrite(DRIVER_EN, HIGH);
  attachInterrupt(digitalPinToInterrupt(LEFT_ENC_A),  leftISR,  CHANGE);
  attachInterrupt(digitalPinToInterrupt(RIGHT_ENC_A), rightISR, CHANGE);
  Serial.println(F("# drivetrain_test ready (OPEN-LOOP + encoder count). L<pwm> R<pwm> / stop / z"));
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') { if (n > 0) { buf[n] = '\0'; parse(buf); n = 0; apply(); } }
    else if (n < sizeof(buf) - 1) buf[n++] = c;
  }
  uint32_t now = millis();
  if (now - lastPrint >= 200) {
    lastPrint = now;
    noInterrupts(); long lc = leftCount, rc = rightCount; interrupts();
    Serial.print(F("L")); Serial.print(outL);
    Serial.print(F(" R")); Serial.print(outR);
    Serial.print(F(" | EL")); Serial.print(lc);
    Serial.print(F(" ER"));   Serial.print(rc);
    Serial.print(F(" | La")); Serial.print(digitalRead(LEFT_ENC_A));
    Serial.print(F(" Lb"));   Serial.print(digitalRead(LEFT_ENC_B));
    Serial.print(F(" Ra"));   Serial.print(digitalRead(RIGHT_ENC_A));
    Serial.print(F(" Rb"));   Serial.print(digitalRead(RIGHT_ENC_B));
    Serial.println();
  }
}
