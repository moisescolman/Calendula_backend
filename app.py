from src.webserver import app
from src.dbcalendula import init_db

if __name__ == "__main__":
    init_db()  
    app.run(host='0.0.0.0', port=50001, debug=True)  
