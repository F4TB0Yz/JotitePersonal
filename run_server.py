import uvicorn
import os

if os.path.exists(".env"):
    print("Cargando variables desde .env...")
    with open(".env", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip('"').strip("'")

if __name__ == "__main__":
    print("Iniciando J&T Express Web Reporter...")
    print("Por favor, abre tu navegador en: http://localhost:8000")
    uvicorn.run("src.web_ui.main_web:app", host="0.0.0.0", port=8000, reload=True)
