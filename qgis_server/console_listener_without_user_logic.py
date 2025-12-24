import sys
import json
import traceback
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime
import psycopg2

DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
QGIS_DB_URI = os.getenv("QGIS_DB_URI")

# ================================
# QGIS INITIALIZATION
# ================================
from qgis.core import (
    QgsApplication,
    QgsVectorLayer,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsProcessingModelAlgorithm,
    QgsProject,
    QgsDataSourceUri,
    QgsProviderRegistry,
)
from qgis.PyQt.QtCore import QVariant, QDateTime, QDate, QTime

# Correct QGIS initialization BEFORE importing processing
QgsApplication.setPrefixPath("/usr", True)
qgs = QgsApplication([], False)
qgs.initQgis()

# Append QGIS processing path
sys.path.append("/usr/share/qgis/python/plugins")
from processing.core.Processing import Processing
import processing

Processing.initialize()

HOST = "0.0.0.0"
PORT = 8102

# ================================
# LOAD PROJECT AND MODEL
# ================================

model_path = "/scripts/Найкоротший_маршрут_бордюри_з_стилями_2.model3"
project_path = "/scripts/test_algorithm_project_3_16.qgz"

print("Loading QGIS project...")
project = QgsProject.instance()

if not project.read(project_path):
    print("Warning: Failed to load QGIS project, continuing without project...")
else:
    print("Project loaded successfully.")

# Print layers in project for debugging
print("\n=== LAYERS IN PROJECT ===")
for layer_id, layer in project.mapLayers().items():
    print(f"  - {layer.name()} ({layer.id()})")

# Load model
print("\nLoading model...")
model = QgsProcessingModelAlgorithm()
if not model.fromFile(model_path):
    raise RuntimeError(f"Failed to load model from: {model_path}")

print(f"Model loaded: {model.name()}")

# Show parameters
print("\n=== MODEL PARAMETERS ===")
for param in model.parameterDefinitions():
    print(f"- '{param.name()}' ({param.description()})")

# ================================
# HELPERS
# ================================
def convert_value(v):
    if v is None or isinstance(v, QVariant):
        return None
    if isinstance(v, QDateTime):
        return v.toPyDateTime()
    if isinstance(v, QDate):
        return v.toPyDate()
    if isinstance(v, QTime):
        return v.toPyTime()
    return v

# ================================
# REQUEST HANDLER
# ================================
class QgisHandler(BaseHTTPRequestHandler):

    def _send_json(self, status, obj):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(obj).encode())

    def log_message(self, format, *args):
        print("%s [%s] %s" % (
            self.client_address[0],
            self.log_date_time_string(),
            format % args
        ))

    def do_POST(self):
        print(f"\n[{datetime.now()}] Incoming POST → {self.path}")

        if self.path != "/run":
            self._send_json(404, {"error": "Not Found"})
            return

        try:
            length = int(self.headers.get("Content-Length"))
            data = json.loads(self.rfile.read(length).decode())

            max_height = data.get("height")
            start_point = data.get("start")
            route_key = data.get("route_key")

            if None in (max_height, start_point, route_key):
                self._send_json(400, {"error": "Missing required fields"})
                return

            # ================================
            # PREPARE PARAMETERS
            # ================================
            
            # Try to find destinations layer in project first
            
            
            # Prepare all parameters
            params = {
                "": float(max_height),  # Максимальна висота долання, cм
                " (2)": start_point,    # Пункт старту
                "1": QGIS_DB_URI,
                
                # Output parameters
                "native:difference_1:Мережа": 'TEMPORARY_OUTPUT',
                "native:extractbyattribute_2:Мережа маршрутів до об'єктів": 'TEMPORARY_OUTPUT',
                "native:extractbyexpression_1:Найкоротший маршрут": "TEMPORARY_OUTPUT",
                "native:fieldcalculator_1:Бар'єр": "TEMPORARY_OUTPUT"
            }

            print("\n=== MODEL EXECUTION PARAMETERS ===")
            for key, value in params.items():
                if isinstance(value, QgsVectorLayer):
                    print(f"{key}: [Vector Layer] {value.name()} ({value.featureCount()} features)")
                else:
                    print(f"{key}: {value}")

            # ================================
            # EXECUTE MODEL
            # ================================
            context = QgsProcessingContext()
            feedback = QgsProcessingFeedback()
            
            # Add project to context
            context.setProject(project)
            
            print("\nExecuting model...")
            
            try:
                results = processing.run(model, params, context=context, feedback=feedback)
            except Exception as e:
                print(f"Error executing model: {e}")
                # Try alternative - run with model ID
                print("Trying alternative execution method...")
                results = processing.run(model.id(), params, context=context, feedback=feedback)
            
            if not isinstance(results, dict):
                raise RuntimeError(f"Model returned unexpected format: {type(results)}")

            print("Model executed successfully!")
            print(f"Output keys: {list(results.keys())}")

            # ================================
            # FIND ROUTE LAYER
            # ================================
            

            # ================================
            # INSERT TO POSTGRES
            # ================================
            route_layer: QgsVectorLayer = results["native:extractbyexpression_1:Найкоротший маршрут"]

            if route_layer is None or not route_layer.isValid():
                self._send_json(500, {"error": "Temporary route layer not produced"})
                return

            conn = psycopg2.connect(
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                host=DB_HOST,
                port=DB_PORT
            )
            cur = conn.cursor()

            fields = route_layer.fields()
            field_names = fields.names()

            for feat in route_layer.getFeatures():
                geom_wkb = feat.geometry().asWkb()
                raw_attrs = feat.attributes()
                attrs = {field_names[i]: convert_value(raw_attrs[i]) for i in range(len(field_names))}

                def get(name):
                    return attrs.get(name)

                cur.execute("""
                    INSERT INTO geo_score_schema.shortest_routes_history (
                        geom,
                        id, name, address,
                        created_at, created_by, description,
                        last_verified_at, last_verified_by,
                        organization_id, overall_accessibility_score,
                        rejection_reason, status, updated_at, updated_by,
                        location_type_id, image_service_id, start, "end",
                        cost, cost1, route_key
                    )
                    VALUES (
                        ST_SetSRID(%s::geometry, 5564),
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s,
                        %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s
                    )
                """, (
                    psycopg2.Binary(geom_wkb),
                    get("id"),
                    get("name"),
                    get("address"),
                    get("created_at"),
                    get("created_by"),
                    get("description"),
                    get("last_verified_at"),
                    get("last_verified_by"),
                    get("organization_id"),
                    get("overall_accessibility_score"),
                    get("rejection_reason"),
                    get("status"),
                    get("updated_at"),
                    get("updated_by"),
                    get("location_type_id"),
                    get("image_service_id"),
                    get("start"),
                    get("end"),
                    get("cost"),
                    get("cost1"),
                    route_key
                ))

            conn.commit()
            cur.close()
            conn.close()

            self._send_json(200, {"status": "ok"})


        except Exception as e:
            error_trace = traceback.format_exc()
            print(f"\n❌ ERROR in do_POST: {error_trace}")
            self._send_json(500, {
                "error": str(e),
                "traceback": error_trace
            })

# ================================
# START SERVER
# ================================
def start_server():
    print(f"\n[{datetime.now()}] QGIS HTTP server starting at {HOST}:{PORT}")
    print("=" * 60)
    print("Server is ready to accept requests")
    print("POST JSON to: http://localhost:8102/run")
    print("Example JSON:")
    print('''{
  "height": 5,
  "start": "6380562.644879097,5707672.514904286",
  "route_key": "17915a57-43bf-4538-831d-6fec7244411x"
}''')
    print("=" * 60)
    
    server = HTTPServer((HOST, PORT), QgisHandler)
    print(f"[{datetime.now()}] QGIS HTTP server started on port {PORT}")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"\n[{datetime.now()}] Server stopped by user")
    except Exception as e:
        print(f"\n[{datetime.now()}] Server error: {e}")
    finally:
        qgs.exitQgis()

if __name__ == "__main__":
    try:
        start_server()
    except Exception as e:
        print(f"Fatal error: {e}")
        qgs.exitQgis()