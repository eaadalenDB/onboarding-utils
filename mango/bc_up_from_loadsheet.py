import pandas as pd
import json
import re
import os

# --- Configuration & Constants ---
OBJ_TYPE_MAP = {
    'AI': 'ANALOG_INPUT',
    'AO': 'ANALOG_OUTPUT',
    'AV': 'ANALOG_VALUE',
    'BI': 'BINARY_INPUT',
    'BO': 'BINARY_OUTPUT',
    'BV': 'BINARY_VALUE'
}

def main():
    # --- Prompts ---
    loadsheet_file = input("Please enter the absolute file path for the loadsheet (e.g., /path/to/loadsheet.xlsx): ").strip()
    aspid_file = input("Please enter the absolute file path for the ASPID map (e.g., /path/to/aspid.xlsx): ").strip()
    publisher_xid = input("Please enter the publisherXid (e.g., PUB_UDMI_BACNET_CGW_1): ").strip()

    # --- Determine Output Directory ---
    # Extract the directory from the provided loadsheet path
    output_dir = os.path.dirname(loadsheet_file)
    
    # Construct absolute paths for the output files
    bacnet_out_file = os.path.join(output_dir, 'bacnet_config.json')
    udmi_out_file = os.path.join(output_dir, 'udmi_publisher.json')

    # --- Load Data ---
    print(f"\nLoading data from:\n - {loadsheet_file}\n - {aspid_file}\n")
    try:
        df_loadsheet = pd.read_excel(loadsheet_file)
        df_aspid = pd.read_excel(aspid_file)
    except Exception as e:
        print(f"Error reading Excel files: {e}")
        return

    # Create a dictionary for assetName -> proxy_id mapping
    asset_to_proxy = dict(zip(df_aspid['asset_name'], df_aspid['proxy_id']))

    bacnet_data_points = []
    udmi_published_points = []

    # --- Process Rows ---
    for index, row in df_loadsheet.iterrows():
        # 1. Filter: Process only where required = "YES"
        if str(row.get('required')).strip().upper() != 'YES':
            continue

        asset_name = str(row.get('assetName')).strip()
        
        # 2. Map Asset to Proxy ID
        if asset_name not in asset_to_proxy:
            print(f"ERROR: Asset name '{asset_name}' not found in ASPID map. Skipping row {index + 2}.")
            continue
            
        proxy_id = asset_to_proxy[asset_name]
        
        # Extract variables from loadsheet
        raw_device_id = str(row.get('deviceId'))
        # Extract only the numerical digits from 'DEV:2706117'
        device_id_digits = re.sub(r'\D', '', raw_device_id) 
        
        raw_obj_type = str(row.get('objectType')).strip().upper()
        expanded_obj_type = OBJ_TYPE_MAP.get(raw_obj_type, raw_obj_type)
        
        # Fix for Pandas float-casting (e.g., converting 2.0 to int 2)
        raw_obj_id = row.get('objectId')
        try:
            object_id_int = int(float(raw_obj_id))
            object_id_str = str(object_id_int)
        except (ValueError, TypeError):
            # Fallback just in case the objectId is an unexpected string
            object_id_str = str(raw_obj_id).strip()
            object_id_int = object_id_str
            
        standard_field_name = str(row.get('standardFieldName')).strip()

        # 3. Generate XID
        xid = f"DP_{device_id_digits}_{expanded_obj_type}_{object_id_str}"

        # --- Build BACnet Config Object ---
        bacnet_point = {
            "xid": xid,
            "name": standard_field_name,
            "enabled": True,
            "loggingType": "INTERVAL",
            "intervalLoggingPeriodType": "MINUTES",
            "intervalLoggingType": "AVERAGE",
            "purgeType": "YEARS",
            "pointLocator": {
                "dataType": "NUMERIC",
                "objectType": expanded_obj_type,
                "propertyIdentifier": "present-value",
                "objectInstanceNumber": object_id_int,
                "remoteDeviceInstanceNumber": int(device_id_digits) if device_id_digits.isdigit() else device_id_digits,
                "settable": False
            },
            "dataSourceXid": "DS_BACNET",
            "deviceName": proxy_id,
            "tags": {
                "BACnetDeviceName": proxy_id,
                "BACnetObjectName": standard_field_name,
                "BACnetPropertyName": "present-value",
                "proxy_id": proxy_id,
                "BACnetObjectDescription": standard_field_name
            }
        }
        bacnet_data_points.append(bacnet_point)

        # --- Build UDMI Publisher Object ---
        udmi_point = {
            "name": standard_field_name,
            "enabled": True,
            "dataPointXid": xid,
            "deviceName": proxy_id,
            "publisherXid": publisher_xid
        }
        udmi_published_points.append(udmi_point)

    # --- Write Output Files ---
    bacnet_output = {"dataPoints": bacnet_data_points}
    udmi_output = {"publishedPoints": udmi_published_points}

    with open(bacnet_out_file, 'w', encoding='utf-8') as f:
        json.dump(bacnet_output, f, indent=3)
        
    with open(udmi_out_file, 'w', encoding='utf-8') as f:
        json.dump(udmi_output, f, indent=2)

    print(f"\nSuccess! Generated output in {output_dir}:")
    print(f" - bacnet_config.json ({len(bacnet_data_points)} points)")
    print(f" - udmi_publisher.json ({len(udmi_published_points)} points)")

if __name__ == "__main__":
    main()