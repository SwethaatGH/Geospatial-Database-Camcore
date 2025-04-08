# Steps to run API:

1. Make sure you are connected to a University WiFi (or using VPN)
2. Ensure you have Postgres and POSTGIS Downloaded and added to path. Refer to readme in data upload for steps. 
3. Establish ssh tunnel to connect to postgis db on Camcore premises. 
`ssh -L 5433:localhost:5432 user@remote.example.com`  
4. Create venv
5. Run `pip install -r .\app\requirements.text` to your venv
6. Start dev server: `uvicorn app.main:app --reload` 
7. To obtain temporary URL use ngrok 

## Checklist:
- [ ] Scale Factors Add 
- [ ] Date Validation
- [ ] Latitude Validation
- [ ] Add TerraClim
- [ ] Add Soil Grids
- [ ] Add elev
- [ ] Add NASA Power
