from app import app
from app import db
from datetime import datetime
from datetime import date
# part of timeline 
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.ALLOWED_EXTENSIONS


def process_test_data(input):
    # print('process', input)
    output = {}
    # print("PPB TO PPM CONVERSION COMPLETE", dirty.data['po4_ppm'],  3.066*int(dirty.data['po4_ppb'])/1000)
    try:
        for key, value in input.items():
            # print(f"Key: {key}, Value: {value}")
            if not value:
                # If value is empty string, set it to None
                value = None
            
            if key == 'po4_ppb' and value is not None or "":
                # Convert PPB to PPM
                output['po4_ppm'] = (3.066 * float(value) / 1000)
                # print("PPB TO PPM CONVERSION COMPLETE", output['po4_ppm'])
            if key != 'test_date' and key != 'test_time' and key != 'oper' and key != 'id':
                # Ignore these keys
                if value is not None:
                    # Convert to float if it's a number
                    # print('check data+', key, value)
                    output[key] = float(value)
                else:
                    # print('check data-', key, value)
                    output[key] = value  

        # print('check data', output)
        # output['id'] = input['id'] if input['id'] else None
        output['id'] = input.get('id', None)
        # print(output)
        output['test_date'] = input['test_date'] if input['test_date'] else date.today().strftime("%Y-%m-%d")
        output['test_time'] = input['test_time'] if input['test_time'] else datetime.now().strftime("%H:%M:%S")

        # print('cleaned', output)   
        assert not output == {}, "data parse error"
        return output
    except:
        print('error cleaning data')
        print(output)
    return {}


def process_dosing_data(input):
    output = {} 

    for key, value in input.items():
        if value == '':
            # If value is empty string, set it to None
            value = None
        if key != 'added_on' and key != 'dosed_at' and key != 'oper' and key != 'id':
            # Ignore these keys
            if value is not None:
                # Convert to float if it's a number
                output[key] = float(value)
            else:
                output[key] = value
    output['id'] = input.get('id', None)
    output['added_on'] = input['added_on'] if input['added_on'] else date.today().strftime("%Y-%m-%d")
    output['dosed_at'] = input['dosed_at'] if input['dosed_at'] else datetime.now().strftime("%H:%M:%S")

    return output

def process_product_data(input):
    output = {}

    for key, value in input.items():
        if value == '':
            # If value is empty string, set it to None
            value = None
        if key in ['total_volume', 'current_avail'] and value is None:
            output[key] = 0
            continue
        if key != 'id':
            # Ignore these keys
            if value is not None:
                # Convert to float if it's a number
                try:
                    output[key] = float(value)
                except ValueError:
                    output[key] = value
            else:
                output[key] = value
    output['id'] = input.get('id', None)

    if 'used_amt' in output:
        del output['used_amt']

    
    return output

def get_table_columns(table_model):
    """
    Returns a list of column names for the given SQLAlchemy table model.
    
    :param table_model: SQLAlchemy model class
    :return: List of column names
    """
    try:
        return [column.name for column in table_model.__table__.columns]
    except AttributeError:
        print(f"Error: {table_model} is not a valid SQLAlchemy model.")
        return []


def generate_columns(column_names):
    """
    Generates a list of dictionaries for DataTables columns.

    :param column_names: List of column names (e.g., ['id', 'test_date', 'test_time'])
    :return: List of dictionaries with "label" and "data" keys
    """
    return [{"label": col.replace("_", " ").title(), "data": col} for col in column_names]


def validate_and_process_data(model, data):
    """
    Validates and processes data based on the provided SQLAlchemy model.

    :param model: SQLAlchemy model class (e.g., TestModel, DosingModel)
    :param data: Dictionary containing the data to validate and process
    :return: Processed data dictionary or None if validation fails
    """
    try:
        print(f"Validating data for model: {model.__tablename__}")
        print(f"Data: {data}")
        if model.__tablename__ == 'test_results':  
            return process_test_data(data)
        elif model.__tablename__ == 'manual_dosing':  
            return process_dosing_data(data)
        elif model.__tablename__ == 'products':
            return process_product_data(data)
        else:
            raise ValueError(f"No validation function defined for model: {model.__tablename__}")
    except Exception as e:
        print(f"Error validating data for model {model.__tablename__}: {e}")
        return None