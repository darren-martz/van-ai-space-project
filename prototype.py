import json
import os

from google import genai


def calculate_vehicle_cost(purchase_price: int, m_y1: int, m_y2: int, m_y3: int, m_y4: int):
    months_to_own = 48
    years_to_own = months_to_own // 12

    try:

        # Initial depreciation if the vehicle is new (industry standard of 10% off the lot)
        vehicle_value = int(purchase_price) * 0.9

        # Depreciate the vehicle value each year (industry standard 10% per year)
        for _ in range(years_to_own):
            vehicle_value *= 0.9

        # Calculate the total maintenance and energy costs with inflation
        total_maintenance_cost = m_y1 + m_y2 + m_y3 + m_y4

        # Calculate the total cost
        total_cost = int(purchase_price) - vehicle_value + total_maintenance_cost
        cost_per_month = total_cost / months_to_own

        data = {
            'purchase price': int(purchase_price),
            'price_of_vehicle_sold': int(vehicle_value),
            'total_cost_of_maintenance': int(total_maintenance_cost),
            'actual_cost_per_month': int(cost_per_month)
        }
        return data
    except Exception as e:
        print(f"An error occurred in the calculator: {e}")
        return {}


def extract_json_from_string(text):
    pos = text.find("{")
    txt1 = text[pos:]
    pos = txt1.rfind("}")
    txt2 = txt1[:pos + 1]

    try:
        json_data = json.loads(txt2)
        return json_data
    except json.JSONDecodeError as e:
        pos = text.find("[")
        txt1 = text[pos:]
        pos = txt1.rfind("]")
        txt2 = txt1[:pos + 1]

        print("** expected a dictionary, got a list **")

        try:
            json_data = json.loads(txt2)
            return {"items": json_data}
        except json.JSONDecodeError as e:
            print(e)
            return None


def write_list_to_json(data, filename):
    """Writes a list of strings to a JSON file.

    Args:
      data: The list of strings to write.
      filename: The name of the JSON file.
    """
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)  # type: ignore


def read_list_from_json(filename):
    """Reads a list of strings from a JSON file.

    Args:
      filename: The name of the JSON file.

    Returns:
      A list of strings.
    """
    with open(filename, 'r') as f:
        data = json.load(f)
    return data


def collect_data():
    prompt = """
    using public information, list all car and truck manufacturers producing for the north american market in 2024 and 2025. 
    Output the list of manufacturers as a JSON object with no other text. The format will be as follows:
    {
        "manufacturers": ["manufacturer1", "manufacturer2", ...]        
    }
    """
    try:
        manufacturer_filename = "manufacturers.json"

        api_key = os.getenv("GENAI_API_KEY")
        client = genai.Client(api_key=api_key)

        ### Check if the manufacturers data is already available
        if os.path.exists(manufacturer_filename):
            manufacturers = read_list_from_json(manufacturer_filename)
        else:
            response = client.models.generate_content(
                model='gemini-2.0-flash-exp', contents=prompt
            )
            content = response.text.strip()
            manufacturers = extract_json_from_string(content)
            if manufacturers is None:
                raise Exception("Failed to extract JSON data from the response.")
            write_list_to_json(manufacturers, manufacturer_filename)

        ### Collect vehicle data for each manufacturer
        for mf in manufacturers['manufacturers']:
            if manufacturers.get(mf.lower()):
                continue

            prompt = f"""
                using public information, create a list of all make, model, and badge of each vehicle produced by '{mf}' in the current year and next year if available.
                Output the list as a JSON object with no other text. The format will be as follows:
                {{
                    "vehicles": [
                        {{
                            "year": "year",
                            "make": "make1",
                            "model": "model1",                            
                        }}
                    ]
                }}
            """
            print(f"Collecting data for {mf}...")
            response = client.models.generate_content(
                model='gemini-2.0-flash-exp', contents=prompt
            )
            content = response.text.strip()
            vehicles = extract_json_from_string(content)
            if vehicles is None:
                raise Exception("Failed to extract JSON data from the response.")
            manufacturers[mf.lower()] = vehicles['vehicles']
            write_list_to_json(manufacturers, manufacturer_filename)

        ### Collect vehicle data for each manufacturer
        for mf in manufacturers['manufacturers']:
            for vehicle in manufacturers[mf.lower()]:
                year = vehicle['year']
                make = vehicle['make'] or ""
                model = vehicle['model'] or ""

                key = f"{year}-{make or "".lower()}-{model or "".lower()}"

                if os.path.exists(f"data/{key}.json"):
                    continue

                prompt = f"""
                using public information, collect information about the vehicle '{make} {model}' produced by '{mf}' in the year {year}.
                Distance is always in km. Price is always in USD. 
                Include an entry for each badge of the vehicle. 
                All numbers are to not include commas.
                Include one collection of keywords that describe the vehicles demographic for activities, interests, relationships, and opinions.                
                Output the list as a JSON object with no other text. The format will be as follows:
                [
                    "vehicles": [
                        {{
                            "year": "year",
                            "make": "make1",
                            "model": "model1",
                            "badge": "badge1",
                            "price": "0",
                            "energytype": "electric",
                            "maxrange": "0",
                            "MPG": "0",
                            "MPGe": "0",
                            "cost_of_tires": "0",
                            "maintenance_year1": "0",
                            "maintenance_year2": "0",
                            "maintenance_year3": "0",
                            "maintenance_year4": "0",  
                            "major_issue_probability: "0.0",
                            "major_issue_cost": "0",
                            "major_issue_description": "description",  
                            "keywords": ["keyword1", "keyword2", ...]                                                            
                        }}, 
                        {{...}}
                    ]
                ]
                """
                print(f"Collecting data for {year} {make} {model}...")

                try:
                    response = client.models.generate_content(
                        model='gemini-2.0-flash-exp', contents=prompt,
                    )
                    content = response.text.strip()
                    vehicle_list = extract_json_from_string(content)
                    if vehicle_list is None:
                        raise Exception("Failed to extract JSON data from the response.")

                    for item in vehicle_list['vehicles']:
                        item['calculate_vehicle_cost'] = calculate_vehicle_cost(
                            int(item['price']),
                            int(item['maintenance_year1']),
                            int(item['maintenance_year2']),
                            int(item['maintenance_year3']),
                            int(item['maintenance_year4'])
                        )

                    write_list_to_json(vehicle_list, f"data/{key}.json")
                except Exception as e:
                    print(f"An error occurred: {e}")
                    return f"An error occurred: {e}"

        return manufacturers
    except Exception as e:
        return f"An error occurred: {e}"


data = collect_data()
print(data)
