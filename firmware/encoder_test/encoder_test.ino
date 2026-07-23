/*
 * Mouse Droid (MSE-6) - ENCODER bench test (DIAGNOSTIC)
 *
 * NOT the flight firmware and NOT the motor test. This reads the two wheel
 * encoders and prints live counts + raw A/B pin levels. No motors are driven.
 *
 * Use it for the "one full revolution" check: zero the counts, rotate a wheel
 * exactly one turn by hand, read the delta. Uses the SAME pins and the SAME
 * count logic (CHANGE of A, compared with B for direction) as the flight
 * firmware, so the result carries straight over.
 *   6 PPR x 2 edges (CHANGE of A) x 30:1 gearbox = 360 counts / wheel rev.
 *
 * Pairs with tools/encoder_test.py.
 *
 * ---- Serial (115200 baud) ----
 *   Send 'z'  -> zero both counts.
 *   Prints every 200 ms:
 *     "ENC L<count> R<count> | La<0/1> Lb<0/1> Ra<0/1> Rb<0/1>"
 *   The A/B levels help diagnose a dead/loose B channel: turn a wheel slowly and
 *   both that side's A and B levels must toggle 0<->1. If B never changes, the
 *   direction logic cancels pulses and the count sticks near 0.
 *
 * Pins (Uno): D2/D4 = LEFT A/B (D2 interrupt), D3/D7 = RIGHT A/B (D3 interrupt).
 */

const uint8_t LEFT_ENC_A  = 2;   // interrupt
const uint8_t LEFT_ENC_B  = 4;
const uint8_t RIGHT_ENC_A = 3;   // interrupt
const uint8_t RIGHT_ENC_B = 7;

volatile long leftCount  = 0;
volatile long rightCount = 0;

void leftISR() {
  if (digitalRead(LEFT_ENC_A) == digitalRead(LEFT_ENC_B)) leftCount++;
  else                                                    leftCount--;
}
void rightISR() {
  if (digitalRead(RIGHT_ENC_A) == digitalRead(RIGHT_ENC_B)) rightCount++;
  else                                                      rightCount--;
}

uint32_t lastPrint = 0;

void setup() {
  Serial.begin(115200);
  pinMode(LEFT_ENC_A, INPUT_PULLUP);  pinMode(LEFT_ENC_B, INPUT_PULLUP);
  pinMode(RIGHT_ENC_A, INPUT_PULLUP); pinMode(RIGHT_ENC_B, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(LEFT_ENC_A),  leftISR,  CHANGE);
  attachInterrupt(digitalPinToInterrupt(RIGHT_ENC_A), rightISR, CHANGE);
  Serial.println(F("# encoder_test ready. Send 'z' to zero. ~360 counts/wheel-rev."));
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == 'z' || c == 'Z') { noInterrupts(); leftCount = 0; rightCount = 0; interrupts(); }
  }
  uint32_t now = millis();
  if (now - lastPrint >= 200) {
    lastPrint = now;
    noInterrupts(); long lc = leftCount, rc = rightCount; interrupts();
    Serial.print(F("ENC L")); Serial.print(lc);
    Serial.print(F(" R"));    Serial.print(rc);
    Serial.print(F(" | La")); Serial.print(digitalRead(LEFT_ENC_A));
    Serial.print(F(" Lb"));   Serial.print(digitalRead(LEFT_ENC_B));
    Serial.print(F(" Ra"));   Serial.print(digitalRead(RIGHT_ENC_A));
    Serial.print(F(" Rb"));   Serial.print(digitalRead(RIGHT_ENC_B));
    Serial.println();
  }
}
