import uvicorn

if __name__ == "__main__":
    print("Iniciando J&T Express Web Reporter...")
    print("Por favor, abre tu navegador en: http://localhost:8000")
    uvicorn.run("src.web_ui.main_web:app", host="0.0.0.0", port=8000, reload=True)
