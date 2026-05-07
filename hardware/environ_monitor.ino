#include <DHT.h>

// --- Sensor Pin Definitions ---
#define DHTPIN 2            // DHT11 signal pin connected to digital pin 2
#define DHTTYPE DHT11       // Sensor type DHT11
#define gasSensor A0        // MQ-135 analog output connected to A0

// --- Initialize DHT sensor ---
DHT dht(DHTPIN, DHTTYPE);

void setup() {
  Serial.begin(9600);       // Initialize serial communication
  dht.begin();              // Start the DHT sensor
  delay(2000);              // Give sensors some time to stabilize
}

void loop() {
  // --- Read sensor values ---
  float temperature = dht.readTemperature();  // Read temperature in Celsius
  float humidity = dht.readHumidity();        // Read humidity
  int airQuality = analogRead(gasSensor);     // Read air quality level

  // --- Check for valid DHT reading ---
  if (isnan(temperature) || isnan(humidity)) {
    Serial.println("ERROR: Failed to read from DHT sensor!");
    delay(2000);
    return;
  }

  // --- Classify air quality (optional) ---
  String airStatus = "Unknown";
  if (airQuality < 200) {
    airStatus = "Good";
  } else if (airQuality >= 200 && airQuality < 300) {
    airStatus = "Moderate";
  } else {
    airStatus = "Poor";
  }

  // --- Print data in Raspberry Pi friendly format ---
  Serial.print("TEMP:");
  Serial.print(temperature);
  Serial.print(",HUM:");
  Serial.print(humidity);
  Serial.print(",AIR:");
  Serial.print(airQuality);
  Serial.print(",STATUS:");
  Serial.println(airStatus);

  delay(2000); // Delay between readings
}
