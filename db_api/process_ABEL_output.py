import yaml
import os
import sys
from collections import OrderedDict


# ----------------------------
# YAML helpers
# ----------------------------
def write_yaml(file_path, data):
    """Write YAML with OrderedDict handling, true/false -> ON/OFF, and spacing."""
    def convert(obj):
        if isinstance(obj, OrderedDict):
            return {k: convert(v) for k, v in obj.items()}
        elif isinstance(obj, dict):
            return {k: convert(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert(i) for i in obj]
        else:
            return obj

    normal_dict = convert(data)
    with open(file_path, "w") as f:
        yaml.safe_dump(normal_dict, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    # Post-process: replace true/false with ON/OFF and add blank lines between top-level entries
    with open(file_path, "r") as f:
        lines = f.readlines()

    new_lines = []
    for i, line in enumerate(lines):
        line = line.replace("true", "ON").replace("false", "OFF")
        new_lines.append(line)
        if i + 1 < len(lines):
            next_line = lines[i + 1]
            if line.strip() and not line.startswith(" ") and next_line.strip() and not next_line.startswith(" "):
                new_lines.append("\n")

    with open(file_path, "w") as f:
        f.writelines(new_lines)


# ----------------------------
# Lowercase update_mask fields
# ----------------------------
def lowercase_update_mask(guid_dict):
    for guid, content in guid_dict.items():
        if isinstance(content, dict) and "update_mask" in content:
            content["update_mask"] = [x.lower() for x in content["update_mask"]]


# ----------------------------
# Categorize GUIDs
# ----------------------------
def categorize_guids(config):
    update_reporting, update_virtual, add_virtual = OrderedDict(), OrderedDict(), OrderedDict()
    conflicts = []

    for guid, content in config.items():
        if not isinstance(content, dict):
            continue
        categories = []
        if "translation" in content:
            categories.append("reporting")
        if "links" in content:
            op = content.get("operation")
            if op == "UPDATE":
                categories.append("update_virtual")
            elif op == "ADD":
                categories.append("add_virtual")
        if len(categories) > 1:
            conflicts.append((guid, categories))
        elif categories:
            cat = categories[0]
            if cat == "reporting":
                update_reporting[guid] = content
            elif cat == "update_virtual":
                update_virtual[guid] = content
            elif cat == "add_virtual":
                add_virtual[guid] = content

    return update_reporting, update_virtual, add_virtual, conflicts


# ----------------------------
# Expand links
# ----------------------------
def expand_links(entity_dict, original_config):
    added_guids = OrderedDict()
    for guid, content in list(entity_dict.items()):
        if "links" not in content:
            continue
        for linked_guid in content["links"]:
            if linked_guid in added_guids or linked_guid in entity_dict:
                continue
            if linked_guid not in original_config:
                print(f"WARNING: Linked GUID {linked_guid} not found in original config.")
                continue
            linked_content = original_config[linked_guid]
            if "links" in linked_content:
                print(f"ERROR: Linked GUID {linked_guid} contains links. Recursive links not allowed.")
                sys.exit(1)
            # Copy all fields except 'operation' and 'update_mask'
            copied_content = {k: v for k, v in linked_content.items() if k not in ("operation", "update_mask")}
            added_guids[linked_guid] = copied_content
    entity_dict.update(added_guids)


# ----------------------------
# Prepend header
# ----------------------------
def prepend_header(entity_dict, config_metadata, building_guid, building_content):
    new_dict = OrderedDict()
    new_dict["CONFIG_METADATA"] = config_metadata
    new_dict[building_guid] = building_content
    new_dict.update(entity_dict)
    return new_dict


# ----------------------------
# Split functions
# ----------------------------
def split_guids_no_links_from_dict(entity_dict, output_folder, category_name, config_metadata, building_guid, building_content):
    """Split in-memory dict into individual GUID files (no links)."""
    os.makedirs(output_folder, exist_ok=True)
    file_counter = 1

    for guid, content in entity_dict.items():
        if guid in ("CONFIG_METADATA", building_guid):
            continue
        if isinstance(content, dict) and "links" in content:
            continue

        new_dict = OrderedDict()
        new_dict["CONFIG_METADATA"] = config_metadata
        new_dict[building_guid] = building_content
        new_dict[guid] = content

        out_name = f"{category_name}_config_pt{file_counter}.yaml"
        out_path = os.path.join(output_folder, out_name)
        write_yaml(out_path, new_dict)
        file_counter += 1


def split_guids_with_links_from_dict(entity_dict, output_folder, category_name, config_metadata, building_guid, building_content):
    """Split in-memory dict into files for GUIDs with links."""
    os.makedirs(output_folder, exist_ok=True)
    file_counter = 1

    for guid, content in entity_dict.items():
        if not isinstance(content, dict) or "links" not in content:
            continue

        new_dict = OrderedDict()
        new_dict["CONFIG_METADATA"] = config_metadata
        new_dict[building_guid] = building_content
        new_dict[guid] = content

        for linked_guid in content["links"]:
            if linked_guid not in entity_dict:
                print(f"WARNING: Linked GUID {linked_guid} not found in config.")
                continue
            linked_content = entity_dict[linked_guid]
            if "links" in linked_content:
                print(f"ERROR: Linked GUID {linked_guid} has its own links field. Recursive links not allowed.")
                sys.exit(1)
            copied_content = {k: v for k, v in linked_content.items() if k not in ("operation", "update_mask")}
            new_dict[linked_guid] = copied_content

        out_name = f"{category_name}_config_pt{file_counter}.yaml"
        out_path = os.path.join(output_folder, out_name)
        write_yaml(out_path, new_dict)
        file_counter += 1


# ----------------------------
# Main processing function
# ----------------------------
def process_file(input_file):
    config = None
    with open(input_file, "r") as f:
        config = yaml.safe_load(f)

    config_metadata = config.get("CONFIG_METADATA", {"operation": "UPDATE"})
    building_guid, building_content = None, None
    for guid, content in config.items():
        if isinstance(content, dict) and content.get("type") == "FACILITIES/BUILDING":
            building_guid, building_content = guid, content
            break
    if not building_guid:
        print("ERROR: No FACILITIES/BUILDING GUID found in input file.")
        sys.exit(1)

    processing_pool = {k: v for k, v in config.items() if k not in ("CONFIG_METADATA", building_guid)}

    # Step 1: Categorize
    update_reporting, update_virtual, add_virtual, conflicts = categorize_guids(processing_pool)
    if conflicts:
        for guid, cats in conflicts:
            print(f"ERROR: GUID {guid} qualifies for multiple categories: {cats}")
        sys.exit(1)

    # Step 2: Expand links for virtual entities
    expand_links(update_virtual, config)
    expand_links(add_virtual, config)

    # Step 3: Prepend header
    update_reporting = prepend_header(update_reporting, config_metadata, building_guid, building_content)
    update_virtual = prepend_header(update_virtual, config_metadata, building_guid, building_content)
    add_virtual = prepend_header(add_virtual, config_metadata, building_guid, building_content)

    # Step 4: Lowercase update_mask fields
    lowercase_update_mask(update_reporting)
    lowercase_update_mask(update_virtual)
    lowercase_update_mask(add_virtual)

    # Step 5: Split directly from dicts
    base_dir = os.path.dirname(input_file)
    categories = [
        ("update_reporting_entities", update_reporting, False, "update_reporting"),
        ("update_virtual_entities", update_virtual, True, "update_virtual"),
        ("add_virtual_entities", add_virtual, True, "add_virtual"),
    ]

    for folder_name, content, use_links_split, category_name in categories:
        category_folder = os.path.join(base_dir, folder_name)
        if use_links_split:
            split_guids_with_links_from_dict(content, category_folder, category_name,
                                            config_metadata, building_guid, building_content)
        else:
            split_guids_no_links_from_dict(content, category_folder, category_name,
                                           config_metadata, building_guid, building_content)

    print("Processing and splitting complete.")
    print("Split files written to subfolders in:", base_dir)


# ----------------------------
# Entry point
# ----------------------------
if __name__ == "__main__":
    input_file = input("Enter the absolute path to the yaml file exported by ABEL: ").strip()
    if not os.path.isfile(input_file):
        print(f"ERROR: File not found: {input_file}")
        sys.exit(1)
    process_file(input_file)



