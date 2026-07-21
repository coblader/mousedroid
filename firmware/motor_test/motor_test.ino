/*
 * Mouse Droid (MSE-6) - OPEN-LOOP motor / BTS7960 bench test (DIAGNOSTIC)
 *
 * NOT the flight firmware. Use this to verify driver wiring + motor direction
 * WITHOUT the PID loop or the encoders (so a flaky encoder can't cause runaway
 * PWM windup during a first spin). Once each side spins the correct direction
 * AND the encoders read correctly, go back to mouse_droid_controller.ino.
 *
 * Like enc_test, this is a bench diagnostic - it does not have to be committed.
 *
 * ---- Serial (115200 baud, newline-terminated) ----
 *   "L<pwm>"        raw PWM to LEFT driver,  -255..255   (e.g. L120, L-120)
 *   "R<pwm>"        raw PWM to RIGHT driver, -255..255
 *   "L120 R120"     both at once
 *   "stop"          both to 0
 *
 * Positive PWM here == the same direction the flight firmware calls "forward"
 * (PWM on RPWM, LPWM 0), so any lead-swap you make now stays correct there.
 */

const uint8_t LEFT_RPWM  = 5;
const uint8_t LEFT_LPWM  = 6;
const uint8_t RIGHT_RPWM = 9;
const uint8_t RIGHT_LPWM = 10;
const uint8_t DRIVER_EN   = 8;   // all four BTS7960 enables tied here

int outL = 0, outR = 0;
char buf[32];
uint8_t n = 0;

void drive(uint8_t rp, uint8_t lp, int o) {
  o = constrain(o, -255, 255);
  if (o >= 0) { analogWrite(rp, o); analogWrite(lp, 0); }
  else        { analogWrite(rp, 0); analogWrite(lp, -o); }
}

void apply() {
  drive(LEFT_RPWM,  LEFT_LPWM,  outL);
  drive(RIGHT_RPWM, RIGHT_LPWM, outR);
}

void parse(char *s) {
  if (strncasecmp(s, "stop", 4) == 0) { outL = outR = 0; return; }
  for (char *p = s; *p; p++) {
    if      (*p == 'L' || *p == 'l') outL = atoi(p + 1);
    else if (*p == 'R' || *p == 'r') outR = atoi(p + 1);
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(LEFT_RPWM, OUTPUT);  pinMode(LEFT_LPWM, OUTPUT);
  pinMode(RIGHT_RPWM, OUTPUT); pinMode(RIGHT_LPWM, OUTPUT);
  pinMode(DRIVER_EN, OUTPUT);
  apply();                       // 0 PWM before enabling
  digitalWrite(DRIVER_EN, HIGH); // enable drivers
  Serial.println(F("# motor_test ready (OPEN-LOOP, no PID). L<pwm> R<pwm> / stop"));
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (n > 0) {
        buf[n] = '\0'; parse(buf); n = 0;
        apply();
        Serial.print(F("L")); Serial.print(outL);
        Serial.print(F(" R")); Serial.println(outR);
      }
    } else if (n < sizeof(buf) - 1) {
      buf[n++] = c;
    }
  }
}
