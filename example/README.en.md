# End-to-End Example: Melbourne Housing Price Prediction

> Deep integration of Traditional ML (LightGBM) with Large Language Model AI (OpenClaw)
>
> Orchestrated entirely via OpenClaw through WeChat on a mobile phone — zero manual coding.

## Data Source

The Melbourne housing dataset comes from [Kaggle: Melbourne Housing Market](https://www.kaggle.com/datasets/anthonypino/melbourne-housing-market), containing approximately 35,000 property transaction records with 20+ fields including Suburb, Rooms, Price, Distance, Landsize, BuildingArea, and more.

Data was compiled from publicly available information on Domain.com.au, spanning through May 2018.

## Project Files

| File | Description |
|----|----|
| `Melbourne_housing_FULL.csv` | Raw Kaggle dataset (~35,000 rows with missing values) |
| `Melbourne_housing_Pre.py` | Data preprocessing: missing value imputation, feature engineering (log price transform, year/type encoding), outlier filtering |
| `Melbourne_housing_pre.csv` | Cleaned dataset after preprocessing (~9,000 rows, 14 features) |
| `Melbourne_housing_LGBM.py` | LightGBM regression training and tuning (includes Bayesian Optimization + Hyperopt) |
| `demo-1.png` ~ `demo-22.png` | 22-step screenshots of the entire analysis orchestrated via OpenClaw on WeChat |

## Workflow

### Traditional ML Part (Local Scripts)

Preprocessing and model training are **pre-prepared traditional ML code**, demonstrating the depth of classical ML engineering:

```         
Raw Data (35k rows)
    │
    ▼
Melbourne_housing_Pre.py          ← Data Preprocessing (932 lines)
    │  • Missing value imputation (Rooms, Bedroom2, Bathroom, Car, Landsize, BuildingArea, YearBuilt)
    │  • Feature engineering: log price transform (LogPrice), year extraction, one-hot encoding for property type
    │  • Data filtering: remove nulls, outliers
    │  • Excluded fields: Address, SellerG, Date, CouncilArea, Regionname (non-numeric)
    ▼
Preprocessed Data (9k rows, 14 features)
    │
    ▼
Melbourne_housing_LGBM.py         ← Model Training & Tuning (558 lines)
    │  • Multi-model comparison: LightGBM, XGBoost, RandomForest, SVM
    │  • Hyperparameter tuning: Bayesian Optimization + Hyperopt
    │  • Feature importance analysis: SHAP
    │  • Outlier removal strategy: 20% deviation filter on training set
    │  • Evaluation metrics: MSE, MAE, RMSE, R²
    ▼
Trained LightGBM Model
```

### LLM AI Part (OpenClaw Orchestration)

With the traditional ML code in place, the entire analysis is **orchestrated via OpenClaw through WeChat on a mobile phone** (note: the demo uses LightGBM with **default parameters** for simple fitting; hyperparameter tuning is outside this demo's scope):

```         
Steps 1-7:  RStudio Data Exploration
    User → "Load the Melbourne housing preprocessed data"
    OpenClaw → r-session.run_code to load CSV
            → r-session.run_code to plot (distribution/correlation/scatter matrix)
            → User views charts on phone

Step 8:   R → CSV Export
    OpenClaw → r-session.export_data("df_ml")
            → CSV written to r2py/ shared directory

Steps 9-10: Jupyter Lab Data Import
    OpenClaw → jupyter-mcp.import_data(...)
    OpenClaw → jupyter-mcp.run_code to execute LightGBM training script
            → Model fitting with default parameters
            → Predict on test set

Step 18:  Python → CSV Export
    OpenClaw → jupyter-mcp.export_data("results")
            → Ground truth vs predictions written to CSV

Steps 19-22: RStudio Result Visualization
    OpenClaw → r-session.import_data(...)
            → r-session.run_code to plot ground truth vs predicted values
            → User sees final results on phone
```

### OpenClaw's Role

```         
┌────────────────────────────────────────────────────────────────┐
│                  WeChat (Mobile)                                │
│  User ↔ Natural Language ↔ OpenClaw                            │
└──────────┬─────────────────────────────────────────────────────┘
           │
  ┌────────▼────────┐
  │  OpenClaw Agent │  ← Translates natural language → MCP tool calls
  │  (embedded)     │
  └────────┬────────┘
           │
     ┌─────┴─────┐
     │           │
  ┌──▼──┐   ┌───▼───┐
  │  R  │   │Python │   ← Traditional ML capabilities
  │mcp  │   │ mcp   │
  │     │   │       │
  │EDA  │   │LightGBM│
  │Plot │   │Default │
  └─────┘   │Params │
            └───────┘
```

1. **Glue Layer** — Connects R's EDA capabilities with Python's ML capabilities, enabling seamless cross-language collaboration
2. **Translator** — Converts natural language commands ("show me what the data looks like") into precise MCP tool calls
3. **Orchestrator** — Manages cross-language data flow (R → CSV → Python → CSV → R) and data exchange
4. **Remote Controller** — Turns WeChat on a mobile phone into the entry point for AI-powered analysis, accessible anytime, anywhere

## Value of This Example

This example demonstrates the fusion of two AI paradigms:

| AI Type | Role | In This Example |
|----|----|----|
| **Traditional ML** | Data fitting, prediction, optimization | Data preprocessing, LightGBM regression, Bayesian hyperparameter tuning, SHAP feature analysis |
| **LLM AI** | Natural language understanding, tool orchestration, workflow management | OpenClaw understands user intent, calls MCP tools, manages cross-language data flow |

> Traditional ML provides **precise numerical prediction capabilities**, while LLM AI provides **flexible understanding and orchestration capabilities**. The two are not substitutes — they are complementary.

## Steps

| Step | Screenshot | Description |
|----|----|----|
| 1 | ![demo-1](demo-1.png) | Talk to OpenClaw on WeChat, check whether r-session and jupyter-mcp are working or not |
| 2 | ![demo-2](demo-2.png) | List all csv data files in the current working directory |
| 3 | ![demo-3](demo-3.png) | Load Melbourne housing data<br>Preview data structure, column names, data types and so on |
| 4 | ![demo-4](demo-4.png) | Rest of preview — target variable, outliers and so on |
| 5 | ![demo-5](demo-5.png) | Plot — price distribution histogram (RStudio Plots panel) and statistical summary<br>min max mean median std skewness |
| 6 | ![demo-6](demo-6.png) | The density plot and its feature description<br>skewness 0.27<br>mean=median<br>nearly normality |
| 7 | ![demo-7](demo-7.png) | Check the normality, not strictly fit, but enough for engineering regression |
| 8 | ![demo-8](demo-8.png) | kurtosis -0.085<br>skewness 0.27<br>Q-Q plot near diagonal line with little divergence at both sides<br>Distribution curve near normality<br>Conclusion: engineering normality |
| 9 | ![demo-9](demo-9.png) | Steps summary of data analysis:<br>No coding by hand, just talk in WeChat, all done by OpenClaw with Rstudio |
| 10 | ![demo-10](demo-10.png) | Send data to Jupyter Lab<br>Preview DataFrame in Python, verify data integrity |
| 11 | ![demo-11](demo-11.png) | Split training (70%) and test (30%) sets<br>Fit a regression model with LightGBM<br>LightGBM indexes |
| 12 | ![demo-12](demo-12.png) | R² 0.90<br>RMSE 0.1686<br>exp(0.1686) =18%<br>Top 5 feature importance:<br>1. Longtitude<br>2. BuildingArea<br>3. Lattitude<br>4. Landsize<br>5. YearBuilt |
| 13 | ![demo-13](demo-13.png) | Fit LightGBM regression model on test set<br>Send predicted LogPrice and true LogPrice back to Rstudio in a DataFrame |
| 14 | ![demo-14](demo-14.png) | Draw a scatter plot ordered by true LogPrice with a -30%~+30% belt |
| 15 | ![demo-15](demo-15.png) | Summary for outliers<br>total 2705<br>outliers out of -30%~30%: 173 (6.40%) |
| 16 | ![demo-16](demo-16.png) | Send the scatter plot to WeChat |
| 17 | ![demo-17](demo-17.png) | The scatter plot is sent to WeChat |
| 18 | ![demo-18](demo-18.png) | View the scatter plot in full screen |
| 19 | ![demo-19](demo-19.png) | Summary of this end-to-end example:<br>Connect LLM AI to ML AI with WeChat on mobile phone, no coding by hand, Rstudio and Jupyter Lab together |
| 20 | ![demo-20](demo-20.png) | The steps taken in this end-to-end example |
| 21 | ![demo-21](demo-21.png) | Key finding:<br>top important features<br>less outliers<br>well fit and prediction |
| 22 | ![demo-22](demo-22.png) | The roles of OpenClaw, Rstudio and Jupyter Lab<br>no coding by hand, all by talking<br>Perfect job, well done! |

## Tools Used

| Steps | MCP Tools Used | Description |
|----|----|----|
| 2-7 | `r-session.list_objects`, `preview_data`, `run_code` | R-side data exploration and visualization |
| 8 | `r-session.export_data` | R → CSV export |
| 9-10 | `jupyter-mcp.import_data`, `preview_data` | CSV → Python import |
| 11-17 | `jupyter-mcp.run_code`, `list_objects` | Python-side modeling and prediction |
| 18 | `jupyter-mcp.export_data` | Python → CSV export |
| 19-22 | `r-session.import_data`, `run_code` | CSV → R import, visualization |
