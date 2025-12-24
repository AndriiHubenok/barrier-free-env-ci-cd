from fastapi import FastAPI, UploadFile
from fastapi.responses import JSONResponse
from transformers import pipeline
from PIL import Image, UnidentifiedImageError
import io

app = FastAPI(title="NSFW Image Classification")

print("Завантаження моделі...")
classifier = pipeline(
    "image-classification",
    model="Falconsai/nsfw_image_detection"
)
print("Модель завантажена")

@app.post("/check-image")
async def check_image(file: UploadFile):
    try:
        if not file.filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            return JSONResponse(
                status_code=400,
                content={"error": "Непідтримуваний формат зображення. Використовуйте JPG, PNG або WebP."}
            )

        image_bytes = await file.read()
        try:
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except UnidentifiedImageError:
            return JSONResponse(
                status_code=400,
                content={"error": "Не вдалося відкрити зображення. Файл може бути пошкоджений."}
            )

        predictions = classifier([img])[0]
        top_result = predictions[0]

        top_label = top_result['label']
        score = top_result['score']

        return {
            "label": top_label,
            "score": score,
            "is_nsfw": top_label.lower() == "nsfw"
        }

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/health")
def health():
    return {"status": "ok"}
