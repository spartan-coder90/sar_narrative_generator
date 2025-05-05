"""
Excel processor for extracting transaction data from Excel files
"""
import pandas as pd
import numpy as np
from datetime import datetime
import re
import json
from typing import Dict, List, Any, Optional
import os
from backend.utils.math_utils import safe_divide
from backend.utils.logger import get_logger
logger = get_logger(__name__)

class ExcelProcessor:
    """Processes transaction Excel files to extract relevant data for SAR narratives"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.workbook = None
        self.sheets = {}
        self.data = {}
        self.sheet_characteristics = {}
        
    def analyze_value(self, value: Any) -> Dict:
        """Analyze a single cell value"""
        if pd.isna(value):
            return {"type": "null", "value": None}
        
        value_str = str(value)
        analysis = {
            "type": type(value).__name__,
            "value": value,
            "length": len(value_str),
        }
        
        # Check for common patterns
        patterns = {
            "currency": r'^\$?\d{1,3}(,\d{3})*(\.\d{2})?$',
            "date_mdy": r'^\d{1,2}/\d{1,2}/\d{2,4}$',
            "date_ymd": r'^\d{4}-\d{2}-\d{2}$',
            "account_number": r'^[A-Z0-9]{8,20}$',
            "percentage": r'^\d+(\.\d+)?%$'
        }
        
        matched_patterns = []
        for pattern_name, pattern in patterns.items():
            if re.match(pattern, value_str):
                matched_patterns.append(pattern_name)
        
        if matched_patterns:
            analysis["patterns"] = matched_patterns
        
        return analysis
    
    def detect_sheet_structure(self, df: pd.DataFrame) -> Dict:
        """Detect the structure of a sheet without assumptions"""
        structure = {
            "shape": df.shape,
            "columns": [],
            "data_patterns": {},
            "possible_headers": [],
            "numeric_columns": [],
            "date_columns": [],
            "text_columns": [],
            "key_value_pairs": [],
            "tables_detected": []
        }
        
        # Analyze each column
        for col_idx, col_name in enumerate(df.columns):
            col_info = {
                "name": col_name,
                "index": col_idx,
                "dtype": str(df[col_name].dtype),
                "null_count": df[col_name].isna().sum(),
                "unique_count": df[col_name].nunique(),
                "sample_values": []
            }
            
            # Get sample values
            non_null_values = df[col_name].dropna()
            if len(non_null_values) > 0:
                sample_size = min(5, len(non_null_values))
                col_info["sample_values"] = non_null_values.head(sample_size).tolist()
            
            # Analyze patterns in this column
            pattern_counts = {}
            for value in non_null_values:
                analysis = self.analyze_value(value)
                for pattern in analysis.get("patterns", []):
                    pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
            
            if pattern_counts:
                col_info["detected_patterns"] = pattern_counts
            
            structure["columns"].append(col_info)
        
        # Detect potential headers/metadata in first N rows
        for i in range(min(10, df.shape[0])):
            row = df.iloc[i]
            non_null_count = row.notna().sum()
            
            # Detect rows that might be headers or metadata
            if non_null_count < len(df.columns) * 0.3:  # Sparse row
                structure["possible_headers"].append({
                    "row_index": i,
                    "type": "sparse",
                    "content": row.dropna().to_dict()
                })
            
            # Check for key-value patterns in rows
            for col in df.columns:
                cell_value = row[col]
                if pd.notna(cell_value):
                    value_str = str(cell_value)
                    if ":" in value_str:
                        parts = value_str.split(":", 1)
                        if len(parts) == 2:
                            structure["key_value_pairs"].append({
                                "row": i,
                                "column": col,
                                "key": parts[0].strip(),
                                "value": parts[1].strip()
                            })
        
        # Detect numeric columns
        for col in df.select_dtypes(include=[np.number]).columns:
            structure["numeric_columns"].append(col)
        
        # Detect date columns
        for col in df.columns:
            try:
                # Try to parse as dates
                pd.to_datetime(df[col], errors='coerce').dropna()
                if len(pd.to_datetime(df[col], errors='coerce').dropna()) > 0:
                    structure["date_columns"].append(col)
            except:
                pass
        
        # Detect text columns
        for col in df.select_dtypes(include=['object']).columns:
            if col not in structure["date_columns"]:
                structure["text_columns"].append(col)
        
        # Attempt to detect tabular data regions
        structure["tables_detected"] = self.detect_tables(df)
        
        return structure
    
    def detect_tables(self, df: pd.DataFrame) -> List[Dict]:
        """Detect tabular structures within the sheet"""
        tables = []
        
        # Look for regions with consistent data
        for start_row in range(df.shape[0]):
            if start_row + 3 > df.shape[0]:  # Need at least 3 rows
                break
                
            # Check if this row could be a header row
            row = df.iloc[start_row]
            non_null_count = row.notna().sum()
            
            if non_null_count >= len(df.columns) * 0.5:  # At least half filled
                # Look for data rows below this
                data_rows = []
                for i in range(start_row + 1, min(start_row + 10, df.shape[0])):
                    data_row = df.iloc[i]
                    if data_row.notna().sum() >= len(df.columns) * 0.3:
                        data_rows.append(i)
                
                if len(data_rows) >= 2:  # Found at least 2 data rows
                    tables.append({
                        "header_row": start_row,
                        "header_content": row.dropna().to_dict(),
                        "data_start_row": data_rows[0],
                        "data_end_row": data_rows[-1],
                        "estimated_rows": len(data_rows)
                    })
        
        return tables
    
    def log_sheet_analysis(self, sheet_name: str, structure: Dict):
        """Log comprehensive sheet analysis"""
        logger.info(f"\n{'='*20} SHEET ANALYSIS: {sheet_name} {'='*20}")
        logger.info(f"Shape: {structure['shape']}")
        
        logger.info("\nCOLUMN SUMMARY:")
        for col in structure['columns']:
            logger.info(f"  Column {col['index']}: '{col['name']}'")
            logger.info(f"    Data type: {col['dtype']}")
            logger.info(f"    Null count: {col['null_count']}")
            logger.info(f"    Unique values: {col['unique_count']}")
            if 'detected_patterns' in col:
                logger.info(f"    Detected patterns: {col['detected_patterns']}")
            logger.info(f"    Sample values: {col['sample_values']}")
        
        if structure['possible_headers']:
            logger.info("\nPOSSIBLE HEADERS/METADATA:")
            for header in structure['possible_headers']:
                logger.info(f"  Row {header['row_index']} ({header['type']}):")
                for k, v in header['content'].items():
                    logger.info(f"    {k}: {v}")
        
        if structure['key_value_pairs']:
            logger.info("\nKEY-VALUE PAIRS DETECTED:")
            for kvp in structure['key_value_pairs'][:10]:  # Show first 10
                logger.info(f"  Row {kvp['row']}, Col '{kvp['column']}': {kvp['key']} = {kvp['value']}")
        
        if structure['tables_detected']:
            logger.info("\nTABLES DETECTED:")
            for i, table in enumerate(structure['tables_detected']):
                logger.info(f"  Table {i+1}:")
                logger.info(f"    Header row: {table['header_row']}")
                logger.info(f"    Headers: {list(table['header_content'].keys())}")
                logger.info(f"    Data rows: {table['data_start_row']} to {table['data_end_row']}")
        
        logger.info("\nDATA TYPE SUMMARY:")
        logger.info(f"  Numeric columns: {structure['numeric_columns']}")
        logger.info(f"  Date columns: {structure['date_columns']}")
        logger.info(f"  Text columns: {structure['text_columns']}")
        
        logger.info(f"\n{'='*60}\n")
    
    def load_workbook(self) -> bool:
        """Load the Excel workbook and analyze its structure"""
        try:
            logger.info(f"\n{'#'*20} EXCEL FILE DISCOVERY {'#'*20}")
            logger.info(f"File path: {self.file_path}")
            logger.info(f"File exists: {os.path.exists(self.file_path)}")
            
            if not os.path.exists(self.file_path):
                logger.error(f"File does not exist: {self.file_path}")
                return False
            
            # Get file size
            file_size = os.path.getsize(self.file_path)
            logger.info(f"File size: {file_size} bytes ({file_size/1024:.2f} KB)")
            
            # Load the workbook
            xlsx = pd.ExcelFile(self.file_path)
            sheet_names = xlsx.sheet_names
            
            logger.info(f"\nDiscovered {len(sheet_names)} sheets:")
            for i, sheet_name in enumerate(sheet_names):
                logger.info(f"  {i+1}. {sheet_name}")
            
            # Load and analyze each sheet
            for sheet_name in sheet_names:
                try:
                    # Read the sheet
                    df = pd.read_excel(xlsx, sheet_name)
                    
                    # Store the raw data
                    self.sheets[sheet_name] = df
                    
                    # Analyze structure
                    structure = self.detect_sheet_structure(df)
                    self.sheet_characteristics[sheet_name] = structure
                    
                    # Log analysis
                    self.log_sheet_analysis(sheet_name, structure)
                    
                except Exception as e:
                    logger.error(f"Error processing sheet {sheet_name}: {str(e)}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error loading Excel file: {str(e)}")
            return False
    
    def search_patterns(self):
        """Search for common patterns across all sheets"""
        logger.info(f"\n{'*'*20} PATTERN SEARCH ACROSS ALL SHEETS {'*'*20}")
        
        # Define patterns to search for
        search_patterns = {
            "total_amount": [r'total.*amount', r'total.*\$', r'amount.*total', r'grand total'],
            "date_range": [r'date.*range', r'from.*to', r'\d{1,2}/\d{1,2}/\d{2,4}.*\d{1,2}/\d{1,2}/\d{2,4}'],
            "suspicious_activity": [r'suspicious', r'unusual', r'alert', r'aml'],
            "transaction_types": [r'transaction.*type', r'type.*transaction', r'cash.*deposit', r'cash.*withdrawal', r'ach', r'wire'],
            "account_number": [r'account.*number', r'account.*#', r'acct.*number'],
            "indicators": [r'indicator', r'aml.*risk', r'structuring', r'layering']
        }
        
        results = {}
        
        for sheet_name, df in self.sheets.items():
            results[sheet_name] = {}
            
            for pattern_name, patterns in search_patterns.items():
                results[sheet_name][pattern_name] = []
                
                # Search in all cells
                for row_idx in range(df.shape[0]):
                    for col_idx in range(df.shape[1]):
                        cell_value = df.iloc[row_idx, col_idx]
                        
                        if pd.notna(cell_value):
                            cell_str = str(cell_value).lower()
                            
                            for pattern in patterns:
                                if re.search(pattern, cell_str):
                                    results[sheet_name][pattern_name].append({
                                        "row": row_idx,
                                        "column": df.columns[col_idx],
                                        "value": cell_value,
                                        "pattern": pattern
                                    })
        
        # Log results
        for sheet_name, sheet_results in results.items():
            logger.info(f"\nPATTERNS FOUND IN SHEET: {sheet_name}")
            for pattern_name, matches in sheet_results.items():
                if matches:
                    logger.info(f"  {pattern_name}: {len(matches)} matches")
                    for match in matches[:3]:  # Show first 3 matches
                        logger.info(f"    Row {match['row']}, Col '{match['column']}': {match['value']}")
        
        return results
    
    def generate_extraction_guide(self):
        """Generate a guide for extracting data based on discovered structure"""
        logger.info(f"\n{'@'*20} EXTRACTION GUIDE {'@'*20}")
        
        for sheet_name, structure in self.sheet_characteristics.items():
            logger.info(f"\nSHEET: {sheet_name}")
            
            # Suggest extraction methods based on detected structure
            if structure["tables_detected"]:
                logger.info("  EXTRACTION METHOD: Table-based")
                for table in structure["tables_detected"]:
                    logger.info(f"    Extract table starting at row {table['header_row']}")
                    logger.info(f"    Column mapping: {table['header_content']}")
            
            if structure["key_value_pairs"]:
                logger.info("  EXTRACTION METHOD: Key-value parsing")
                logger.info("    Key-value pairs found - use row-by-row extraction")
            
            if structure["possible_headers"]:
                logger.info("  EXTRACTION METHOD: Custom header handling")
                logger.info("    Headers detected - may need to skip metadata rows")
            
            # Suggest column mappings
            if structure["numeric_columns"]:
                logger.info(f"  Potential AMOUNT columns: {structure['numeric_columns']}")
            
            if structure["date_columns"]:
                logger.info(f"  Potential DATE columns: {structure['date_columns']}")
    
    def process(self) -> Dict[str, Any]:
        """Process the Excel file with complete structural discovery"""
        logger.info("\n" + "="*60)
        logger.info("STARTING EXCEL FILE DISCOVERY AND ANALYSIS")
        logger.info("="*60)
        
        # Load and analyze structure
        if not self.load_workbook():
            logger.error("Failed to load workbook")
            return self.data
        
        # Search for patterns
        pattern_results = self.search_patterns()
        
        # Generate extraction guide
        self.generate_extraction_guide()
        
        # Save raw data for review
        logger.info("\n" + "="*60)
        logger.info("SAVING ANALYSIS RESULTS")
        logger.info("="*60)
        
        # Save comprehensive analysis
        analysis_output = {
            "file_info": {
                "path": self.file_path,
                "size": os.path.getsize(self.file_path)
            },
            "sheets": {}
        }
        
        for sheet_name, df in self.sheets.items():
            analysis_output["sheets"][sheet_name] = {
                "shape": df.shape,
                "columns": list(df.columns),
                "structure": self.sheet_characteristics.get(sheet_name, {}),
                "patterns_found": pattern_results.get(sheet_name, {})
            }
        
        # Save to file for review
        output_path = self.file_path + "_analysis.json"
        try:
            with open(output_path, 'w') as f:
                json.dump(analysis_output, f, indent=2, default=str)
            logger.info(f"Analysis saved to: {output_path}")
        except Exception as e:
            logger.error(f"Error saving analysis: {str(e)}")
        
        return self.data