# Use 3: statistical analysis of the public Greenhand API in a notebook.
# Paste each "# %%" block into its own cell (Jupyter / Google Colab / VS Code).

# %%
import requests
import pandas as pd
import matplotlib.pyplot as plt

API_URL = "https://lexxieliu.pythonanywhere.com/api/summary/"
df = pd.DataFrame(requests.get(API_URL, timeout=10).json())
df

# %%
# Descriptive statistics
df["value"].describe()

# %%
# Share of the collection per category
df["share_pct"] = (df["value"] / df["value"].sum() * 100).round(1)
df.sort_values("value", ascending=False)

# %%
# Visualise it
ax = df.sort_values("value", ascending=False).plot.bar(
    x="category", y="value", legend=False, color="#4CAF50", figsize=(7, 4)
)
ax.set_title("Plants per category (from the public API)")
ax.set_xlabel("Category")
ax.set_ylabel("Plants")
plt.tight_layout()
plt.show()