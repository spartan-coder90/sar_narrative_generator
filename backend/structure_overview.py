"""
Utility script to create a structural overview of Excel analysis JSON
"""
import json
import sys

def create_structure_overview(json_file_path: str):
    """
    Create a clean structural overview of the Excel workbook
    
    Args:
        json_file_path: Path to the full analysis JSON file
    """
    try:
        # Read the full JSON
        with open(json_file_path, 'r') as f:
            full_data = json.load(f)
        
        # Create structural overview
        overview = {
            "total_sheets": len(full_data.get("sheets", {})),
            "sheets": {}
        }
        
        # For each sheet, extract the structure
        for sheet_name, sheet_data in full_data.get("sheets", {}).items():
            structure = sheet_data.get("structure", {})
            
            # Get basic sheet info
            shape = sheet_data.get("shape", (0, 0))
            
            # Get column information
            columns_info = []
            if "columns" in structure:
                for col in structure["columns"]:
                    col_info = {
                        "index": col.get("index", -1),
                        "name": col.get("name", ""),
                        "dtype": col.get("dtype", "unknown"),
                        "null_count": col.get("null_count", 0),
                        "unique_count": col.get("unique_count", 0)
                    }
                    # Include a few sample values to understand content
                    if "sample_values" in col and col["sample_values"]:
                        col_info["sample_values"] = col["sample_values"][:3]
                    
                    columns_info.append(col_info)
            
            # Get detected structures
            detected_structures = {
                "tables": [],
                "key_value_pairs": [],
                "possible_headers": []
            }
            
            # Extract table information
            if "tables_detected" in structure and structure["tables_detected"]:
                for table in structure["tables_detected"]:
                    detected_structures["tables"].append({
                        "header_row": table.get("header_row", -1),
                        "data_start_row": table.get("data_start_row", -1),
                        "data_end_row": table.get("data_end_row", -1),
                        "estimated_rows": table.get("estimated_rows", 0)
                    })
            
            # Extract key-value pairs (first 5)
            if "key_value_pairs" in structure and structure["key_value_pairs"]:
                for kvp in structure["key_value_pairs"][:5]:
                    detected_structures["key_value_pairs"].append({
                        "row": kvp.get("row", -1),
                        "column": kvp.get("column", ""),
                        "key": kvp.get("key", ""),
                        "value": kvp.get("value", "")
                    })
            
            # Extract possible headers (first 3)
            if "possible_headers" in structure and structure["possible_headers"]:
                for header in structure["possible_headers"][:3]:
                    detected_structures["possible_headers"].append({
                        "row_index": header.get("row_index", -1),
                        "type": header.get("type", ""),
                        "content": header.get("content", {})
                    })
            
            # Compile sheet overview
            overview["sheets"][sheet_name] = {
                "dimensions": {
                    "rows": shape[0],
                    "columns": shape[1]
                },
                "column_information": columns_info,
                "detected_structures": detected_structures,
                "data_types": {
                    "numeric_columns": structure.get("numeric_columns", []),
                    "date_columns": structure.get("date_columns", []),
                    "text_columns": structure.get("text_columns", [])
                }
            }
        
        # Save structural overview
        output_file = json_file_path.replace('.json', '_structure_overview.json')
        with open(output_file, 'w') as f:
            json.dump(overview, f, indent=2)
        
        print(f"Structural overview saved to: {output_file}")
        
        # Create a minimal version for quick review
        minimal_overview = {
            "total_sheets": len(full_data.get("sheets", {})),
            "sheet_summaries": {}
        }
        
        for sheet_name, sheet_data in full_data.get("sheets", {}).items():
            shape = sheet_data.get("shape", (0, 0))
            structure = sheet_data.get("structure", {})
            
            minimal_overview["sheet_summaries"][sheet_name] = {
                "dimensions": f"{shape[0]} rows x {shape[1]} columns",
                "column_names": [col.get("name", "") for col in structure.get("columns", [])],
                "has_tables": len(structure.get("tables_detected", [])) > 0,
                "has_key_value_pairs": len(structure.get("key_value_pairs", [])) > 0
            }
        
        # Save minimal overview
        minimal_output_file = json_file_path.replace('.json', '_minimal_overview.json')
        with open(minimal_output_file, 'w') as f:
            json.dump(minimal_overview, f, indent=2)
        
        print(f"Minimal overview saved to: {minimal_output_file}")
        
        return overview, minimal_overview
        
    except Exception as e:
        print(f"Error processing JSON file: {str(e)}")
        return None, None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python structure_overview.py <json_file_path>")
        sys.exit(1)
    
    json_file_path = sys.argv[1]
    create_structure_overview(json_file_path)
