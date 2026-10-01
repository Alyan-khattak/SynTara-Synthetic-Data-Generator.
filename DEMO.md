# HackDataV2 Demo Script

## 1. Tabular Mode Demo
1. Start the server: `python app.py`
2. Open `http://localhost:8000` in your browser.
3. Select **Tabular** on the left menu.
4. Type in the query: `10 users with name, age, and email address.`
5. Click **Generate**.
6. Wait for the generation to finish and preview the results in the table viewer.

## 2. Relational Mode Demo
1. Select **Relational** on the left menu.
2. Type in the query: `An e-commerce store with 20 customers, 50 orders, and 100 order items.`
3. Click **Generate**.
4. You will see multiple tables in the preview (customers, orders, order_items). Notice that the order table correctly references customer ids.

## 3. Data Mode (Cloning) Demo
1. Select **Data Mode** on the left menu (wait, frontend uses `data_mode` module name).
2. The UI switches to a file upload input.
3. Upload a CSV file (e.g., `tests/data.csv` if available, or create a simple CSV with a few numerical and categorical columns).
4. The backend splits the data 80/20, fits a Gaussian Copula to the numerical columns, and generates a synthetic clone.
5. Review the resulting **Scorecard** showing the Fidelity, Utility, and Privacy metrics. 

## 4. Exporting Data
1. Find any completed run in the **Run History** table at the bottom.
2. Click **Download**.
3. A `.zip` file will be downloaded containing your CSV files (or the singular synthetic data CSV).
