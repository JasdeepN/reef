from app import app
from app import db
from datetime import datetime
from datetime import date
import sqlalchemy   

# part of timeline 
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.ALLOWED_EXTENSIONS


def process_test_data(input):
    print('process', input)
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
    allowed = {'_time', 'amount', 'id', 'product_id', 'tank_id', 'schedule_id'}
    for key, value in input.items():
        if key not in allowed:
            continue
        if value == '' or value is None:
            output[key] = None
            continue
        if key == 'amount':
            try:
                output[key] = float(value)
            except Exception:
                output[key] = None
        elif key in ['product_id', 'id', 'tank_id']:
            try:
                output[key] = int(value)
            except Exception:
                output[key] = None
        elif key == '_time':
            from datetime import datetime
            try:
                if isinstance(value, datetime):
                    output[key] = value
                else:
                    output[key] = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            except Exception:
                try:
                    output[key] = datetime.strptime(value, "%Y-%m-%d")
                except Exception:
                    output[key] = None
    return output

def process_product_data(input):
    output = {}
    # Only allow fields that exist in Products (excluding computed/relationship fields)
    allowed = {'name', 'dose_amt', 'total_volume', 'current_avail', 'dry_refill', 'last_refill'}
    for key, value in input.items():
        if key not in allowed:
            continue
        if value == '' or value is None:
            output[key] = None
            continue
        if key in ['dose_amt', 'total_volume', 'current_avail', 'dry_refill']:
            try:
                output[key] = float(value)
            except Exception:
                output[key] = None
        elif key == 'last_refill':
            # Accept both date and datetime strings
            try:
                if isinstance(value, (datetime, date)):
                    output[key] = value
                else:
                    # Try parsing as datetime first, then date
                    try:
                        output[key] = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
                    except Exception:
                        output[key] = datetime.strptime(value, "%Y-%m-%d")
            except Exception:
                output[key] = None
        else:
            output[key] = value
    return output

def process_schedule_data(input):
    output = {}
    allowed = {'product_id', 'amount', 'last_trigger', 'trigger_interval', 'suspended', 'last_refill', 'tank_id'}
    for key, value in input.items():
        print(f"Key: {key}, Value: {value}")
        if key not in allowed:
            continue
        if value == '' or value is None:
            output[key] = None
            continue
        if key in ['amount']:
            try:
                output[key] = float(value)
            except Exception:
                output[key] = None
        elif key in ['trigger_interval']:
            try:
                output[key] = int(value)
            except Exception:
                output[key] = None
        elif key == 'product_id':
            try:
                output[key] = int(value)
            except Exception:
                output[key] = None
        elif key in ['trigger_time']:
            try:
                if isinstance(value, datetime):
                    output[key] = value
                else:
                    output[key] = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            except Exception:           
                output[key] = None
        elif key == 'suspended':
            output[key] = bool(value) if isinstance(value, bool) else value in ['1', 'true', 'True', 'yes', 'on']
        elif key == 'tank_id':
            try:
                output[key] = int(value)
            except Exception:
                output[key] = None
        else:
            output[key] = value
    return output

#####
# Column names for DataTables
#####
# for singe table
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


def get_query_column_names_from_tuple_list_simple(rows):
    if not rows or not isinstance(rows[0], sqlalchemy.engine.row.Row):
        return []
    column_names = []
    for item in rows[0]:
        for col in type(item).__table__.columns:
            column_names.append(col.key)
    return column_names


def get_query_column_names_from_tuple_list(rows):
    """
    Given a list of tuples from a joined SQLAlchemy ORM query,
    returns a list of column names in the format 'model_column' (e.g., 'dosing_id', 'products_name').
    """
    if not rows or not isinstance(rows[0], sqlalchemy.engine.row.Row) :
        print("Error: The provided rows are not in the expected format.")
        return []
    column_names = []
    for item in rows[0]:
        model = type(item)
        prefix = model.__tablename__
        for col in model.__table__.columns:
            column_names.append(f"{prefix}_{col.key}")
    return column_names

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
        elif model.__tablename__ == 'dosing':  
            return process_dosing_data(data)
        elif model.__tablename__ == 'products':
            return process_product_data(data)
        elif model.__tablename__ == 'd_schedule':
            return process_schedule_data(data)
        else:
            raise ValueError(f"No validation function defined for model: {model.__tablename__}")
    except Exception as e:
        print(f"Error validating data for model {model.__tablename__}: {e}")
        return None

def advanced_join_query(
    db,
    TABLE_MAP,
    table_names,
    join_type="inner",  # "inner", "left", "right", "full"
    join_conditions=None,
    filters=None,       # list of SQLAlchemy filter expressions
    order_by=None,      # list of (table, column, direction)
    limit=None,
    offset=None,
    params=None,       # DataTables parameters
):
    """
    Build and execute a flexible join query with optional filters, ordering, and pagination.

    :param db: SQLAlchemy db instance
    :param TABLE_MAP: dict mapping table names to model classes
    :param table_names: list of table names to join
    :param join_type: join type ("inner", "left", "right", "full")
    :param join_conditions: list of SQLAlchemy join conditions (len = n-1 for n tables)
    :param filters: list of SQLAlchemy filter expressions
    :param order_by: list of (table_name, column_name, direction) tuples
    :param limit: int
    :param offset: int
    :return: list of dicts (rows)
    """

    if not table_names or len(table_names) < 2:
        raise ValueError("At least two tables required for join.")
    if join_conditions is None or len(join_conditions) != len(table_names) - 1:
        raise ValueError("Number of join conditions must be one less than number of tables.")

    models = [TABLE_MAP[name] for name in table_names]
    query = db.session.query(*models)

    # Apply joins
    for idx, condition in enumerate(join_conditions):
        right_model = models[idx + 1]
        if join_type == "left":
            query = query.outerjoin(right_model, condition)
        elif join_type == "right":
            # SQLAlchemy does not support right join directly; swap tables and use left join
            query = query.select_from(right_model).outerjoin(models[idx], condition)
        elif join_type == "full":
            query = query.join(right_model, condition, isouter=True, full=True)
        else:  # default to inner join
            query = query.join(right_model, condition)

    # Apply filters
    if filters:
        for f in filters:
            query = query.filter(f)

    # Apply ordering
    if order_by:
        for table_name, col_name, direction in order_by:
            model = TABLE_MAP[table_name]
            col = getattr(model, col_name)
            if direction.lower() == "desc":
                query = query.order_by(col.desc())
            else:
                query = query.order_by(col.asc())

    # Pagination
    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    # print ("Executing query:", str(query))
    results = query.all()

    # print("Query results:", results)
    # Serialize results
    import enum
    from datetime import date, time
    data = []
    for row in results:
        row_dict = {}
        for item in row:
            model = type(item)
            prefix = model.__tablename__
            for col in model.__table__.columns:
                val = getattr(item, col.key)
                if isinstance(val, enum.Enum):
                    row_dict[f"{prefix}_{col.key}"] = val.value
                elif isinstance(val, date):
                    row_dict[f"{prefix}_{col.key}"] = val.strftime("%Y-%m-%d")
                elif isinstance(val, time):
                    row_dict[f"{prefix}_{col.key}"] = val.strftime("%H:%M:%S")
                else:
                    row_dict[f"{prefix}_{col.key}"] = val
        data.append(row_dict)

    return data

def apply_datatables_query_params_to_dicts(data, params):
    # print("Applying DataTables query params to data")
    """
    Applies DataTables sorting, ordering, filtering, and search to a list of dicts (rows).

    :param data: List of dicts (rows)
    :param params: dict containing DataTables parameters:
        - search: global search string
        - sidx: column to sort by
        - sord: sort direction ('asc' or 'desc')
        - page: page number (1-based)
        - rows: number of rows per page
    :return: (filtered_data, total_records)
    """
    # Filtering (global search)
    if params is None:
        
        params = {
            'search': '',  
            'sidx': '',
            'sord': 'asc',
            'page': 1,
            'rows': 10
        }
    search = params.get('search', '').lower()
    if search:
        def row_matches(row):
            return any(search in str(value).lower() for value in row.values() if value is not None)
        data = list(filter(row_matches, data))

    # Ordering
    sidx = params.get('sidx')
    sord = params.get('sord', 'asc')
    # print(params)
    if sidx:
        def sort_key(x):
            val = x.get(sidx, None)
            # Treat None as less than any value, and try to convert to float if possible
            if val is None:
                return float('-inf') if sord == 'asc' else float('inf')
            try:
                return float(val)
            except (ValueError, TypeError):
                return str(val)
        data = sorted(
            data,
            key=sort_key,
            reverse=(sord == 'desc')
        )

    # Total records after filtering
    total_records = len(data)

    # Pagination
    page = int(params.get('page', 1))
    rows = int(params.get('rows', 10))
    start = (page - 1) * rows
    end = start + rows
    data = data[start:end]

    return data, total_records

def datatables_response(data, params, draw):
    """
    Applies DataTables search, ordering, and pagination to a list of dicts,
    and returns a response dict ready for jsonify.
    """
    filtered_data, total_filtered = apply_datatables_query_params_to_dicts(data, params)
    # print("Filtered data:", filtered_data)
    response = {
        "draw": draw,
        "recordsTotal": len(data),
        "recordsFiltered": total_filtered,
        "data": filtered_data,
    }
    return response