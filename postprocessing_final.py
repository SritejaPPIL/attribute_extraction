import os
import re
import json
import logging
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
from collections import defaultdict
from tqdm import tqdm

## constants ##
FUZZY_THRESHOLD = 60


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def process_and_save_json(file_path, output_dir, dropdown_values):
    
    def postprocess_string(s):
        try:
            s = s.lower()
            s = re.sub(r'[^a-zA-Z0-9\- \s<>=+]', '', s)
            return s
        except Exception as e:
            logging.error(f"Error in postprocess_string for value {s}: {str(e)}")
            return s
        
    def remove_char_num(string):
        try:
            string = string.replace('-',' ')
            return re.sub(r'[^A-Za-z\s]', '', string).lower().strip()
        except Exception as e:
            logging.error(f"Error in remove_char_num for value {string}: {str(e)}")
            return string

    # def extract_numbers(value, category):
    #     try:
    #         if value is None or str(value).upper() == "NONE":
    #             return None
    #         value = str(value).replace(',', '')
    #         numbers = re.findall(r'\d+', value)
    #         return list(map(int, numbers)) if numbers else [value]  # Return single int or original value
    #     except (ValueError, TypeError) as e:
    #         logging.error(f"Error extracting numbers from value {value}: {str(e)}")

    def extract_numbers(value, category=None):
        try:
            if value is None or str(value).upper() == "NONE":
                return None
            
            value = str(value).replace(',', '')
            
            # Define patterns for each category
            patterns = {
                'cri': r'(\d+)\s*(?:CRI|RA|R[Aa])',
                'cct': r'(\d+)\s*K',
                'lumens': r'(\d+)\s*(?:LM|LUMENS?)',
            }
            
            # If a category is specified, try to extract it
            if category:
                category = category.lower()  # Convert to lowercase
                if category in patterns:
                    match = re.search(patterns[category], value, re.IGNORECASE)
                    if match:
                        return [int(match.group(1))]
            
            # If no category specified or no match found, look for any of the patterns
            for cat, pattern in patterns.items():
                match = re.search(pattern, value, re.IGNORECASE)
                if match:
                    return [int(match.group(1))]
            
            # If no specific pattern found, extract all numbers
            numbers = re.findall(r'\d+', value)
            if numbers:
                return list(map(int, numbers))
            
            return []
        except (ValueError, TypeError) as e:
            logging.error(f"Error extracting numbers from value {value}: {str(e)}")
            return []

    def postprocess_voltage(extracted_value, dropdown_values):
        try:
            if extracted_value is None or str(extracted_value).upper() == "NONE":
                return None
            postprocessed_values = []    
            extracted_numbers = sorted(list(map(int, re.findall(r'\d+', extracted_value))))
                
            if len(extracted_numbers) in [1, 2]:
                if min(extracted_numbers) < 12:
                    postprocessed_values.append('Other Low Voltage')
                if max(extracted_numbers) > 480:
                    postprocessed_values.append('Other High Voltage')
                for value in dropdown_values:
                    dropdown_numbers = sorted(list(map(int, re.findall(r'\d+', value))))
                    if len(dropdown_numbers) > 0:
                        if min(extracted_numbers) == min(dropdown_numbers) and max(extracted_numbers) == max(dropdown_numbers):
                            postprocessed_values.append(value)
            else:
                
                dropdown_values_lower = [value.lower() for value in dropdown_values]
                extracted_value_lower = extracted_value.lower().replace('universal', 'unv')
                
                if 'unv' in extracted_value_lower:
                    postprocessed_values.append('120-277v UNV / MVOLT')
                    
                threshold = FUZZY_THRESHOLD
                postprocessed_voltage, voltage_score = list(process.extractOne(extracted_value_lower, dropdown_values_lower))
            
                if voltage_score >= threshold:
                    dropdown_index = dropdown_values_lower.index(postprocessed_voltage)
                    postprocessed_values.append(dropdown_values[dropdown_index])
        
            return list(set(postprocessed_values)) if len(postprocessed_values) > 0 else [extracted_value]
        except Exception as e:
            logging.error(f"Error in postprocess_voltage for value {extracted_value}: {str(e)}")
            return [extracted_value]
            
    
            
    def postprocess_mounting(extracted_value, dropdown_values):
        
        try:
            if extracted_value is None or str(extracted_value).upper() == "NONE":
                return None
            postprocessed_values = []
            for value in dropdown_values:
                sub_values = [v.lower().replace('-', ' ').strip() for v in value.split('/')]
        
                if any(sub_value in extracted_value.lower().replace('-', ' ').strip() for sub_value in sub_values):
                    postprocessed_values.append(value)
        
                if any(extracted_sub_value in value.lower().replace('-', ' ').strip() for extracted_sub_value in extracted_value.lower().replace('-', ' ').strip().split()):
                    postprocessed_values.append(value)
        
            if len(postprocessed_values) == 0 and len(extracted_value) > 3:
                
                dropdown_values_processed = [remove_char_num(value) for value in dropdown_values]
                extracted_value_processed = remove_char_num(extracted_value)
        
                threshold = FUZZY_THRESHOLD
                postprocessed_mounting, score = list(process.extractOne(extracted_value_processed, dropdown_values_processed))
        
                if score >= threshold:
                    dropdown_index = dropdown_values_processed.index(postprocessed_mounting)
                    postprocessed_values.append(dropdown_values[dropdown_index])
        
            return list(set(postprocessed_values)) if len(postprocessed_values) > 0 else [extracted_value]
            
        except Exception as e:
            logging.error(f"Error in postprocess_mounting for value {extracted_value}: {str(e)}")
            return [extracted_value]

    def postprocess_environment(extracted_value, dropdown_values):
        try:
            if extracted_value is None or str(extracted_value).upper() == "NONE":
                return None
            postprocessed_values = []
            wet_values = ['IP67', 'IP65', 'IP66', 'IP68', 'IP69K', 'Pool / Spa','Marine']
        
            for value in dropdown_values:
                sub_values = [v.lower().strip() for v in value.split('/')]
        
                if any(sub_value in extracted_value.lower().strip() for sub_value in sub_values):
                    postprocessed_values.append(value)
                    if value == 'Wet':
                        postprocessed_values.extend(wet_values)
                    
                if any(extracted_sub_value in value.lower().strip() for extracted_sub_value in extracted_value.lower().replace('/', '').replace('-', '').strip().split()):
                    postprocessed_values.append(value)
                    if value == 'Wet':
                        postprocessed_values.extend(wet_values)
        
        
            if len(postprocessed_values) == 0 and len(extracted_value) > 3:
                
                dropdown_values_processed = [remove_char_num(value) for value in dropdown_values]
                extracted_value_processed = remove_char_num(extracted_value)
        
                threshold = FUZZY_THRESHOLD
                postprocessed_environment, score = list(process.extractOne(extracted_value_processed, dropdown_values_processed))
                if score >= threshold:
                    dropdown_index = dropdown_values_processed.index(postprocessed_environment)
                    postprocessed_values.append(dropdown_values[dropdown_index])
        
            return list(set(postprocessed_values)) if len(postprocessed_values) > 0 else [extracted_value]
        except Exception as e:
            logging.error(f"Error in postprocess_environment for value {extracted_value}: {str(e)}")
            return [extracted_value]

    def postprocess_dpr(extracted_value, dp_dropdown_values, dr_dropdown_values, postprocess_type='dp'):
        try:
            if extracted_value is None or str(extracted_value).upper() == "NONE":
                return None
    
            dp_postprocessed_values, dr_postprocessed_values = [], []
            
            dp_abb_list = ['0-10V', '1-10V', 'Triac', 'ELV', 'MLV', 'Lutron', 'DALI', 'DMX', 'PWM']
    
            if postprocess_type == 'dp':
                indices = [i for i, value in enumerate(dp_abb_list) if value.lower().replace('-', ' ') in extracted_value.lower().replace('-', ' ')]
                dp_abb_fetched = [dp_dropdown_values[i] for i in indices]
                dp_postprocessed_values.extend(dp_abb_fetched)
    
                dp_dropdown_values_processed = [postprocess_string(string) for string in dp_dropdown_values]
                extracted_value_processed = postprocess_string(extracted_value)
    
                postprocessed_dp, dp_score = list(process.extractOne(extracted_value_processed, dp_dropdown_values_processed))
                postprocessed_dp = dp_dropdown_values[dp_dropdown_values_processed.index(postprocessed_dp)]
    
                if dp_score > FUZZY_THRESHOLD:
                    dp_postprocessed_values.append(postprocessed_dp)
    
                return list(set(dp_postprocessed_values)) if dp_postprocessed_values else [extracted_value]
    
            elif postprocess_type == 'dr':
                dr_dropdown_values_processed = [postprocess_string(string) for string in dr_dropdown_values]
                extracted_value_processed = postprocess_string(extracted_value)
    
                postprocessed_dr, dr_score = list(process.extractOne(extracted_value_processed, dr_dropdown_values_processed))
                postprocessed_dr = dr_dropdown_values[dr_dropdown_values_processed.index(postprocessed_dr)]
    
                if dr_score > FUZZY_THRESHOLD:
                    dr_postprocessed_values.append(postprocessed_dr)
    
                return list(set(dr_postprocessed_values)) if dr_postprocessed_values else [extracted_value]
    
            else:
                raise ValueError("Invalid postprocess_type. Expected 'dp' or 'dr'.")
    
        except Exception as e:
            logging.error(f"Error in postprocess_dpr for value {extracted_value}: {str(e)}")
            return [extracted_value], [extracted_value]

                   
    
    def normalize_json(json_data, dropdown_values):
        
        normalized_json = {}
        try:
            for category, attributes in json_data.items():
                if isinstance(attributes, dict):
                    normalized_json[category] = []
                    for key, value in attributes.items():
                        if value is None or str(value).upper() == "NONE":
                            normalized_json[category]= None
                        elif category.lower() in ["cri", "cct", "lumens"]:
                            normalized_json[category].extend(extract_numbers(value, category.lower()))
                            
                        elif category.lower() ==  'dimming protocol':
                            postprocessed_dp = postprocess_dpr(value, dropdown_values['dimming protocol'], dropdown_values['dimming range'], postprocess_type='dp')
                            normalized_json[category].extend(postprocessed_dp)
                        elif category.lower() ==  'dimming range':
                            postprocessed_dr = postprocess_dpr(value, dropdown_values['dimming protocol'], dropdown_values['dimming range'], postprocess_type='dr')
                            normalized_json[category].extend(postprocessed_dr)
                        elif category.lower() == 'mounting type':
                            normalized_json[category].extend(postprocess_mounting(value, dropdown_values['mounting type']))
                        elif category.lower() == 'environment':
                            normalized_json[category].extend(postprocess_environment(value, dropdown_values['environment']))
                        elif category.lower() == 'voltage':
                            normalized_json[category].extend(postprocess_voltage(value, dropdown_values['voltage'])) 
                        else:
                            normalized_json[category].append(value)#
                    #normalized_json['Mounting Type'] = normalized_json.pop('Mounting')
                else:
                    if attributes is None or str(attributes).upper() == "NONE":
                        normalized_json[category] = None

                    elif category.lower() in ["cri", "cct", "lumens"]:
                        normalized_json[category] = extract_numbers(attributes, category.lower())
                    elif category.lower() == 'dimming protocol':
                        postprocessed_dp = postprocess_dpr(value, dropdown_values['dimming protocol'], dropdown_values['dimming range'], postprocess_type='dp')
                        normalized_json[category] = postprocessed_dp
                    elif category.lower() == 'dimming range':
                        postprocessed_dr = postprocess_dpr(value, dropdown_values['dimming protocol'], dropdown_values['dimming range'], postprocess_type='dr')
                        normalized_json[category] = postprocessed_dr
                    elif category.lower() == 'mounting type':
                        normalized_json[category] = postprocess_mounting(attributes, dropdown_values['mounting type'])
                    elif category.lower() == 'environment':
                        normalized_json[category] = postprocess_environment(attributes, dropdown_values['environment'])
                    elif category.lower() == 'voltage':
                        normalized_json[category] = postprocess_voltage(attributes, dropdown_values['voltage'])  
                    else:
                        normalized_json[category] = attributes
            #normalized_json['Mounting Type'] = normalized_json.pop('Mounting')

                    
        except Exception as e:
            logging.error(f"Error normalizing JSON: {str(e)}")
            return {}  # Fallback to empty JSON on error
        return normalized_json

    try:
        # Load the input JSON
        with open(file_path, 'r') as json_file:
            json_data = json.load(json_file)['predicted']
    
        # Normalize the JSON data
        normalized_data = normalize_json(json_data, dropdown_values)
        #print(normalized_data)
    
        # Save the normalized JSON to the output directory
        output_file_path = os.path.join(output_dir, os.path.basename(file_path))
        with open(output_file_path, 'w') as output_file:
            json.dump(normalized_data, output_file, indent=4)
    
        #logging.info(f"Normalized JSON saved to {output_file_path}")
    except FileNotFoundError as fnf_error:
        logging.error(f"File not found: {file_path}. Error: {str(fnf_error)}")
    except json.JSONDecodeError as json_error:
        logging.error(f"Error decoding JSON from file {file_path}: {str(json_error)}")
    except Exception as e:
        logging.error(f"Unexpected error processing file {file_path}: {str(e)}")

def main():
    # Input and output directories
    input_dir = r"/home/sriteja-code/info_table_extraction/trial_8_dropdown_values_added"
    output_dir = r"/home/sriteja-code/info_table_extraction/postprocessed_trial8"

    dropdown_values = {
        "environment": [
            'Healthcare / Patient Rooms', 'Outdoor', 'Hazardous', 'Cleanroom', 'Damp',
            'Classroom / Educational Facilities', 'Wet', 'Food Processing', 'Marine',
            'MRI-Safe', 'Pool / Spa', 'Dry', '2HR Fire Rated', 'ADA', 'IC', 'CA Title 24',
            'CCEA Chicago Plenum', 'Energy Star', 'IP67', 'IP65', 'IP66', 'IP68', 'IP69K',
            'JA8', 'Non-IC'
        ],
        "dimming protocol": [
            '0-10V', '1-10V', 'Triac', 'ELV (Electronic Low Voltage)', 'MLV (Magnetic Low Voltage)',
            'Lutron', 'DALI', 'DMX', 'PWM', 'Forward Phase', 'Reverse Phase', 'Touch', 
            'Pull Chain', 'In-Line On/Off', 'Hand Motion', 'Bulb Dependent', 'UniDim', 
            'Warm Dim / Adjustable White', 'Full Range Dimmer Switch', 'Wireless (Bluetooth, Zigbee, Casambi)'
        ],
        "dimming range": [
            'Bi-Level', 'Dim to <1%', 'Dim to 1%', 'Dim to 5-10%', 'Dim to ≥ 11%', 'Multi Switching',
            'Step Dim', 'Dim-to-Dark', 'Non-Dimmable'
        ],
        "voltage": [
            'Other Low Voltage', '12v', '24v', '12-24v', '36v', '100-110v', '100-240v', '100-277v MVOLT',
            '100-347v', '120-240v', '120-277v UNV / MVOLT', '120-347v', '120v', '120-250v', '125v',
            '200-480v', '220-240v', '277-480v HVOLT', '277v', '347v', '347-480v HVOLT', '400v', '480v',
            'Other High Voltage'
        ],
        "mounting type": [
            'Adjustable', 'Arm', 'Knuckle / Yoke / Trunnion', 'Monopoint', 'Recessed', 'Semi-Recessed', 
            'Surface', 'Wall', 'Ground / Floor', 'Suspended / Cable / Chain / Stem / Pendant', 'T-Bar Grid', 
            'Track', 'Flange / Trimmed', 'Trimless', 'Stake', 'Retrofit', 'Magnetic', 'Pole / Stanchion / Tenon', 
            'Clamp / Hook / Strap'
        ]
    }

    # Loop through JSON files in the input directory
    for json_file in tqdm(os.listdir(input_dir)):
        file_path = os.path.join(input_dir, json_file)
        process_and_save_json(file_path, output_dir, dropdown_values)

if __name__ == "__main__":
    main()