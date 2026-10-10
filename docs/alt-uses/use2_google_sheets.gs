const API_URL = "https://lexxieliu.pythonanywhere.com/api/summary/";

function importPlants() {
  const response = UrlFetchApp.fetch(API_URL);
  const data = JSON.parse(response.getContentText());

  const sheet = SpreadsheetApp.getActiveSheet();
  sheet.clear();

  // Header + one row per category from the API
  sheet.getRange(1, 1, 1, 2).setValues([["category", "value"]]);
  const rows = data.map(item => [item.category, item.value]);
  sheet.getRange(2, 1, rows.length, 2).setValues(rows);

  // Simple aggregations done by Sheets formulas
  const last = rows.length + 1;
  sheet.getRange("D1").setValue("Total plants");
  sheet.getRange("E1").setFormula(`=SUM(B2:B${last})`);
  sheet.getRange("D2").setValue("Largest category");
  sheet.getRange("E2").setFormula(`=INDEX(A2:A${last}, MATCH(MAX(B2:B${last}), B2:B${last}, 0))`);
  sheet.getRange("D3").setValue("Average per category");
  sheet.getRange("E3").setFormula(`=ROUND(AVERAGE(B2:B${last}), 2)`);
}