/*
 * CoD-Style Detection Radar
 * ESP32 + HC-SR04 Ultrasonic Sensor + SG90 Servo + ILI9341 TFT
 *
 * Wiring:
 *   HC-SR04: TRIG -> GPIO 26, ECHO -> GPIO 25
 *   SG90 Servo: Signal -> GPIO 27
 *   ILI9341 TFT (SPI):
 *     MOSI -> GPIO 23, SCLK -> GPIO 18
 *     CS   -> GPIO  5, DC   -> GPIO  2
 *     RST  -> GPIO  4, LED  -> 3.3V
 *   Buzzer (optional): -> GPIO 32
 */

#include <Adafruit_GFX.h>
#include <Adafruit_ILI9341.h>
#include <ESP32Servo.h>
#include <math.h>

// --- Pin Definitions ---
#define TRIG_PIN    26
#define ECHO_PIN    25
#define SERVO_PIN   27
#define BUZZER_PIN  32

#define TFT_CS       5
#define TFT_DC       2
#define TFT_RST      4

// --- Display ---
Adafruit_ILI9341 tft = Adafruit_ILI9341(TFT_CS, TFT_DC, TFT_RST);

// --- Servo ---
Servo radarServo;

// --- Radar Config ---
#define RADAR_MAX_DIST_CM   150   // Max detection range
#define RADAR_ANGLE_STEP      2   // Degrees per sweep step
#define SWEEP_DELAY_MS        8   // ms between steps (controls sweep speed)

// --- Display dimensions ---
#define SCREEN_W  240
#define SCREEN_H  320
#define CENTER_X  (SCREEN_W / 2)        // 120
#define CENTER_Y  (SCREEN_H - 40)       // 280 — radar origin near bottom
#define RADAR_R   110                    // Radius of radar circle in pixels

// --- Colors (ILI9341 16-bit) ---
#define COLOR_BG          0x0000   // Black
#define COLOR_GRID        0x0320   // Dark green
#define COLOR_SWEEP       0x07E0   // Bright green
#define COLOR_OBJECT      0x07E0   // Bright green blip
#define COLOR_OBJECT_FADE 0x0160   // Faded blip trail
#define COLOR_TEXT        0x07E0   // Green text
#define COLOR_ALERT       0xF800   // Red (object too close)
#define COLOR_SWEEP_LINE  0x0680   // Mid-green sweep line

#define ALERT_DIST_CM     40       // Buzz when object closer than this

// --- State ---
int   currentAngle  = 0;
int   sweepDir      = 1;            // 1 = increasing, -1 = decreasing

// Stores last detected distance at each degree (0–180)
float detectedDist[181];
bool  hasObject[181];

// --- Helpers ---

// Convert polar (angle, dist) to screen (x, y)
// angle: 0=right, 90=up, 180=left  (mapped from servo 0-180)
void polarToScreen(int angleDeg, float distCm, int &sx, int &sy) {
  float r = (float)distCm / RADAR_MAX_DIST_CM * RADAR_R;
  r = constrain(r, 0, RADAR_R);
  // Servo 0° = right side, 180° = left side; 90° = straight up (center)
  float rad = (float)(180 - angleDeg) * DEG_TO_RAD;
  sx = CENTER_X + (int)(r * cos(rad));
  sy = CENTER_Y - (int)(r * sin(rad));
}

long measureDistanceCm() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  long duration = pulseIn(ECHO_PIN, HIGH, 30000); // 30ms timeout ~ 5m max
  if (duration == 0) return RADAR_MAX_DIST_CM + 1; // nothing detected
  return duration / 58;
}

void drawGrid() {
  tft.fillScreen(COLOR_BG);

  // Concentric range rings
  int rings = 4;
  for (int i = 1; i <= rings; i++) {
    int r = RADAR_R * i / rings;
    tft.drawCircle(CENTER_X, CENTER_Y, r, COLOR_GRID);
  }

  // Angle spokes every 30°
  for (int a = 0; a <= 180; a += 30) {
    int sx, sy;
    polarToScreen(a, RADAR_MAX_DIST_CM, sx, sy);
    tft.drawLine(CENTER_X, CENTER_Y, sx, sy, COLOR_GRID);
  }

  // Border arc (half circle)
  for (int a = 0; a <= 180; a++) {
    float rad = (float)(180 - a) * DEG_TO_RAD;
    int x = CENTER_X + (int)(RADAR_R * cos(rad));
    int y = CENTER_Y - (int)(RADAR_R * sin(rad));
    tft.drawPixel(x, y, COLOR_SWEEP);
  }

  // Labels
  tft.setTextColor(COLOR_TEXT);
  tft.setTextSize(1);
  tft.setCursor(2, CENTER_Y - 4);  tft.print("180");
  tft.setCursor(SCREEN_W - 22, CENTER_Y - 4); tft.print("0");
  tft.setCursor(CENTER_X - 6, CENTER_Y - RADAR_R - 10); tft.print("90");

  // Range labels
  for (int i = 1; i <= rings; i++) {
    int label = RADAR_MAX_DIST_CM * i / rings;
    int r = RADAR_R * i / rings;
    tft.setCursor(CENTER_X + 2, CENTER_Y - r - 8);
    tft.print(label); tft.print("cm");
  }

  // Title
  tft.setTextSize(2);
  tft.setCursor(60, 4);
  tft.print("RADAR");
  tft.setTextSize(1);
}

void drawStatusBar(int angleDeg, long distCm) {
  // Clear status area
  tft.fillRect(0, SCREEN_H - 30, SCREEN_W, 30, COLOR_BG);
  tft.setTextColor(COLOR_TEXT);
  tft.setTextSize(1);
  tft.setCursor(4, SCREEN_H - 24);
  tft.print("Angle: "); tft.print(angleDeg); tft.print((char)247); // degree symbol

  tft.setCursor(4, SCREEN_H - 12);
  if (distCm > RADAR_MAX_DIST_CM) {
    tft.print("Dist:  ---");
  } else {
    tft.setTextColor(distCm < ALERT_DIST_CM ? COLOR_ALERT : COLOR_TEXT);
    tft.print("Dist:  "); tft.print(distCm); tft.print(" cm");
    if (distCm < ALERT_DIST_CM) {
      tft.setCursor(120, SCREEN_H - 18);
      tft.setTextColor(COLOR_ALERT);
      tft.setTextSize(2);
      tft.print("! NEAR !");
    }
  }
}

void eraseSweepLine(int angleDeg) {
  // Redraw grid line over old sweep to erase it
  int sx, sy;
  polarToScreen(angleDeg, RADAR_MAX_DIST_CM, sx, sy);
  tft.drawLine(CENTER_X, CENTER_Y, sx, sy, COLOR_BG);

  // Redraw any blips that were on this line
  if (hasObject[angleDeg]) {
    polarToScreen(angleDeg, detectedDist[angleDeg], sx, sy);
    tft.fillCircle(sx, sy, 3, COLOR_OBJECT_FADE);
  }

  // Restore grid spokes if we erased one
  if (angleDeg % 30 == 0) {
    polarToScreen(angleDeg, RADAR_MAX_DIST_CM, sx, sy);
    tft.drawLine(CENTER_X, CENTER_Y, sx, sy, COLOR_GRID);
  }
}

void drawSweepLine(int angleDeg) {
  int sx, sy;
  polarToScreen(angleDeg, RADAR_MAX_DIST_CM, sx, sy);
  tft.drawLine(CENTER_X, CENTER_Y, sx, sy, COLOR_SWEEP_LINE);
}

void drawBlip(int angleDeg, float distCm) {
  int sx, sy;
  polarToScreen(angleDeg, distCm, sx, sy);
  tft.fillCircle(sx, sy, 4, COLOR_OBJECT);
}

void setup() {
  Serial.begin(115200);

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(BUZZER_PIN, OUTPUT);

  // Init TFT
  tft.begin();
  tft.setRotation(0);  // Portrait
  drawGrid();

  // Init servo
  radarServo.attach(SERVO_PIN);
  radarServo.write(0);
  delay(500);

  // Clear detection arrays
  for (int i = 0; i <= 180; i++) {
    detectedDist[i] = RADAR_MAX_DIST_CM + 1;
    hasObject[i] = false;
  }
}

void loop() {
  // 1. Move servo to current angle
  radarServo.write(currentAngle);
  delay(SWEEP_DELAY_MS);

  // 2. Erase old sweep line at this angle
  eraseSweepLine(currentAngle);

  // 3. Measure distance
  long dist = measureDistanceCm();

  // 4. Update object memory
  if (dist <= RADAR_MAX_DIST_CM) {
    detectedDist[currentAngle] = (float)dist;
    hasObject[currentAngle] = true;
  } else {
    hasObject[currentAngle] = false;
    detectedDist[currentAngle] = RADAR_MAX_DIST_CM + 1;
  }

  // 5. Draw sweep line
  drawSweepLine(currentAngle);

  // 6. Draw blip if object detected
  if (hasObject[currentAngle]) {
    drawBlip(currentAngle, detectedDist[currentAngle]);

    // Buzz alert for close objects
    if (dist < ALERT_DIST_CM) {
      tone(BUZZER_PIN, 1000, 50);
    }
  }

  // 7. Update status bar
  drawStatusBar(currentAngle, dist);

  // 8. Log to serial
  Serial.printf("Angle: %3d° | Dist: %s\n",
    currentAngle,
    dist > RADAR_MAX_DIST_CM ? "---" : String(dist).c_str());

  // 9. Advance angle
  currentAngle += sweepDir * RADAR_ANGLE_STEP;
  if (currentAngle >= 180) { currentAngle = 180; sweepDir = -1; }
  if (currentAngle <= 0)   { currentAngle = 0;   sweepDir =  1; }
}
