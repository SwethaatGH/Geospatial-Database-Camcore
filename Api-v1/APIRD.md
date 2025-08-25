# Steps to run API:

1. Make sure you are connected to a University WiFi (or using VPN)
2. Ensure you have Postgres and POSTGIS Downloaded and added to path. Refer to readme in data upload for steps. 

On Powershell:
`ssh -L 5433:localhost:5432 Rcavalh@10.72.74.19` 

On cmd:
1. cd Api-v1
<!-- 2. Create venv 'python -m venv venv' -->
<!-- 3. Run `pip install -r .\app\requirementsv1.txt` to your venv -->
4. run: `venv\Scripts\activate`
4. Start dev server: `uvicorn app.main:app --reload` 
6. URL: `http://127.0.0.1:8000/ui` or URL: `http://127.0.0.1:8000/CSVGenerator` or URL: `http://127.0.0.1:8000/docs`
7. ctrl c to quit

