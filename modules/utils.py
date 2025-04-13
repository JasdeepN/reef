from app import app
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
            if value == '':
                # If value is empty string, set it to None
                value = None
            
            if key == 'po4_ppb' and value is not None:
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
        
        output['id'] = input['id'] if input['id'] else None
        output['test_date'] = input['test_date'] if input['test_date'] else date.today().strftime("%Y-%m-%d")
        output['test_time'] = input['test_time'] if input['test_time'] else datetime.now().strftime("%H:%M:%S")

        # print('cleaned', output)   
        assert not output == {}, "data parse error"
        return output
    except:
        print('error cleaning data')
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
    output['id'] = input['id'] if input['id'] else None
    output['added_on'] = input['added_on'] if input['added_on'] else date.today().strftime("%Y-%m-%d")
    output['dosed_at'] = input['dosed_at'] if input['dosed_at'] else datetime.now().strftime("%H:%M:%S")

    return output