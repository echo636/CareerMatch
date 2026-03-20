from app import create_app

app = create_app()

if __name__ == "__main__":
    services = app.config["services"]
    app.run(host="0.0.0.0", port=services.settings.port, debug=services.settings.debug)
