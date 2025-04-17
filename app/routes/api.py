import modules
import json
import datetime
from flask import jsonify, request
from app import app, db
from modules.models import test_results, Products, ManualDosing
from modules.utils import process_test_data
from modules.models import db as models_db  # Import the SQLAlchemy instance from models.py
from sqlalchemy.inspection import inspect

# Dynamically generate TABLE_MAP from models.py
TABLE_MAP = {
    model.__tablename__: model
    for model in models_db.Model.registry._class_registry.values()
    if isinstance(model, type) and hasattr(model, "__tablename__")
}

# @app.route('/api/get_test_results', methods=['GET', 'POST'])
# def get_test_results():
#     try:
#         # Get jqGrid parameters
#         page = int(request.args.get('page', 1))  # Current page number
#         rows = int(request.args.get('rows', 10))  # Number of rows per page
#         sort_column = request.args.get('sidx', 'id')  # Column to sort by
#         sort_order = request.args.get('sord', 'asc')  # Sort order (asc/desc)
#         filters = request.args.get('filters')  # Filtering rules (JSON format)

#         # Base query
#         query = test_results.query

#         # Apply filtering
#         if filters:
#             import json
#             filter_data = json.loads(filters)
#             if filter_data.get('rules'):
#                 for rule in filter_data['rules']:
#                     field = rule['field']
#                     op = rule['op']
#                     value = rule['data']

#                     if op == 'eq':  # Equals
#                         query = query.filter(getattr(test_results, field) == value)
#                     elif op == 'ne':  # Not equals
#                         query = query.filter(getattr(test_results, field) != value)
#                     elif op == 'lt':  # Less than
#                         query = query.filter(getattr(test_results, field) < value)
#                     elif op == 'le':  # Less than or equal
#                         query = query.filter(getattr(test_results, field) <= value)
#                     elif op == 'gt':  # Greater than
#                         query = query.filter(getattr(test_results, field) > value)
#                     elif op == 'ge':  # Greater than or equal
#                         query = query.filter(getattr(test_results, field) >= value)
#                     elif op == 'cn':  # Contains
#                         query = query.filter(getattr(test_results, field).like(f"%{value}%"))

#         # Apply sorting
#         if sort_column and hasattr(test_results, sort_column):
#             if sort_order == 'asc':
#                 query = query.order_by(getattr(test_results, sort_column).asc())
#             else:
#                 query = query.order_by(getattr(test_results, sort_column).desc())

#         # Pagination
#         total_records = query.count()
#         query = query.offset((page - 1) * rows).limit(rows)

#         # Fetch results
#         results = query.all()
#         data = [
#             {
#                 "id": result.id,
#                 "test_date": result.test_date.strftime("%Y-%m-%d") if result.test_date else None,
#                 "test_time": result.test_time.strftime("%H:%M:%S") if result.test_time else None,
#                 "alk": result.alk,
#                 "po4_ppm": result.po4_ppm,
#                 "po4_ppb": result.po4_ppb,
#                 "no3_ppm": result.no3_ppm,
#                 "cal": result.cal,
#                 "mg": result.mg,
#                 "sg": result.sg,
#             }
#             for result in results
#         ]

#         # Prepare response
#         response = {
#             "page": page,
#             "total": (total_records + rows - 1) // rows,  # Total pages
#             "records": total_records,
#             "rows": data,
#         }
#         # print(response)
#         return jsonify(response)
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500

@app.route('/api/edit_test_results', methods=['POST', 'PUT'])
def edit_test_results():
    try:
        print('edit_test_results')
        # Parse JSON data
        try:
            # input = request.get_json()  # Use get_json() to parse JSON
            input = json.loads(request.data, strict=False) #testing
            operation = input.get("oper")  # jqGrid sends 'oper' to indicate the operation (add, edit, del)
       
        except Exception as e:
            print(request)
            print('error parsing json', e)
            return jsonify({"error": str(e)}), 500

        data = modules.utils.process_test_data(input)
        assert data != {}, "no data to insert"

        print( 'operation', operation) 
        if operation == "edit":
            result = test_results.query.get(data["id"])
            result.test_date = data.get("test_date")
            result.test_time = data.get("test_time")
            result.alk = data.get("alk")
            result.po4_ppm = data.get("po4_ppm")
            result.po4_ppb = data.get("po4_ppb")
            result.no3_ppm = data.get("no3_ppm")
            result.cal = data.get("cal")
            result.mg = data.get("mg")
            result.sg = data.get("sg")
            db.session.commit()
        elif operation == "add":
            new_result = test_results(
                test_date=data.get("test_date"),
                test_time=data.get("test_time"),
                alk=data.get("alk"),
                po4_ppm=data.get("po4_ppm"),
                po4_ppb=data.get("po4_ppb"),
                no3_ppm=data.get("no3_ppm"),
                cal=data.get("cal"),
                mg=data.get("mg"),
                sg=data.get("sg"),
            )
           
            db.session.add(new_result)
            db.session.commit()

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# @app.route('/api/delete_test_results', methods=['DELETE'])
# def delete_test_results():
#     try:
#         # Parse JSON data
#         data = request.get_json()
#         test_id = data.get("id")

#         # Find and delete the record
#         result = test_results.query.get(test_id)
#         if result:
#             db.session.delete(result)
#             db.session.commit()
#             return jsonify({"success": True, "message": f"Record with ID {test_id} deleted."})
#         else:
#             return jsonify({"error": f"Record with ID {test_id} not found."}), 404
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500

# @app.route('/api/get_products', methods=['GET'])
# def get_products():
#     try:
#         products = Products.query.order_by(Products.id).all()
#         data = [
#             {
#                 "id": product.id,
#                 "name": product.name,
#                 "dose_amt": product.dose_amt,
#                 "total_volume": product.total_volume,
#                 "current_avail": product.current_avail,
#                 "used_amt": product.used_amt,
#             }
#             for product in products
#         ]
#         return jsonify(data)
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500


@app.route('/api/edit_products', methods=['POST', 'PUT', 'DELETE'])
def edit_products():
    try:
        input = request.get_json()
        operation = input.get("oper")

        if operation == "edit":
            product = Products.query.get(input["id"])
            product.name = input.get("name")
            product.dose_amt = input.get("dose_amt")
            product.total_volume = input.get("total_volume")
            product.current_avail = input.get("current_avail")
            # product.used_amt = input.get("used_amt")
            db.session.commit()
        elif operation == "add":
            new_product = Products(
                name=input.get("name"),
                dose_amt=input.get("dose_amt"),
                total_volume=input.get("total_volume"),
                current_avail=input.get("current_avail"),
                # used_amt=0,  # Assuming used_amt is initialized to 0  
            )
            db.session.add(new_product)
            db.session.commit()
        elif operation == "del":
            product = Products.query.get(input["id"])
            db.session.delete(product)
            db.session.commit()

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# @app.route('/api/get_manual_dosing', methods=['GET'])
# def get_manual_dosing():
#     try:
#         manual_dosing = ManualDosing.query.order_by(ManualDosing.id).all()
#         data = [
#             {
#                 "id": dosing.id,
#                 "added_on": dosing.added_on.strftime("%Y-%m-%d"),
#                 "dosed_at": dosing.dosed_at.strftime("%H:%M:%S"),
#                 "product": dosing.product,
#                 "amount": dosing.amount,
#                 "reason": dosing.reason,
#             }
#             for dosing in manual_dosing
#         ]
#         return jsonify(data)
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500


@app.route('/api/edit_manual_dosing', methods=['POST', 'PUT', 'DELETE'])
def edit_manual_dosing():
    print('edit_manual_dosing')
    
    try:
        input = request.get_json()
        operation = input.get("oper")

        data = modules.utils.process_dosing_data(input)
        
        if operation == "edit":
            dosing = ManualDosing.query.get(input["id"])
            dosing.added_on = data.get("added_on")
            dosing.dosed_at = data.get("dosed_at")
            dosing.product = data.get("product")
            dosing.amount = data.get("amount")
            dosing.reason = data.get("reason")
            db.session.commit()
        elif operation == "add":
            new_dosing = ManualDosing(
                added_on=data.get("added_on"),
                dosed_at=data.get("dosed_at"),
                product=data.get("product"),
                amount=data.get("amount"),
                reason=data.get("reason"),
            )
            db.session.add(new_dosing)
            db.session.commit()
        elif operation == "del":
            dosing = ManualDosing.query.get(input["id"])
            db.session.delete(dosing)
            db.session.commit()

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/delete_row/<table_name>', methods=['DELETE'])
def delete_row(table_name):
    try:
        # Check if the table name exists in the mapping
        if table_name not in TABLE_MAP:
            return jsonify({"error": f"Table '{table_name}' not found."}), 404

        # Parse JSON data
        data = request.get_json()
        row_id = data.get("id")

        if not row_id:
            return jsonify({"error": "No ID provided for deletion."}), 400

        # Get the table model
        table_model = TABLE_MAP[table_name]

        # Find and delete the record
        row = table_model.query.get(row_id)
        if row:
            db.session.delete(row)
            db.session.commit()
            return jsonify({"success": True, "message": f"Record with ID {row_id} deleted from '{table_name}'."})
        else:
            return jsonify({"error": f"Record with ID {row_id} not found in '{table_name}'."}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/get/<table_name>', methods=['GET'])
def get_table_data(table_name):
    try:
        # Check if the table name exists in the mapping
        if table_name not in TABLE_MAP:
            return jsonify({"error": f"Table '{table_name}' not found."}), 404

        # Get the table model
        table_model = TABLE_MAP[table_name]

        # Get jqGrid parameters
        page = int(request.args.get('page', 1))  # Current page number
        rows = int(request.args.get('rows', 10))  # Number of rows per page
        sort_column = request.args.get('sidx', 'id')  # Column to sort by
        sort_order = request.args.get('sord', 'asc')  # Sort order (asc/desc)
        filters = request.args.get('filters')  # Filtering rules (JSON format)

        # Base query
        query = table_model.query

        # Apply filtering
        if filters:
            filter_data = json.loads(filters)
            if filter_data.get('rules'):
                for rule in filter_data['rules']:
                    field = rule['field']
                    op = rule['op']
                    value = rule['data']

                    # Apply filtering logic based on the operator
                    if hasattr(table_model, field):
                        column = getattr(table_model, field)
                        if op == "eq":  # Equals
                            query = query.filter(column == value)
                        elif op == "ne":  # Not equals
                            query = query.filter(column != value)
                        elif op == "lt":  # Less than
                            query = query.filter(column < value)
                        elif op == "le":  # Less than or equal
                            query = query.filter(column <= value)
                        elif op == "gt":  # Greater than
                            query = query.filter(column > value)
                        elif op == "ge":  # Greater than or equal
                            query = query.filter(column >= value)
                        elif op == "cn":  # Contains
                            query = query.filter(column.like(f"%{value}%"))

        # Apply sorting
        if sort_column and hasattr(table_model, sort_column):
            if sort_order == 'asc':
                query = query.order_by(getattr(table_model, sort_column).asc())
            else:
                query = query.order_by(getattr(table_model, sort_column).desc())

        # Pagination
        total_records = query.count()
        query = query.offset((page - 1) * rows).limit(rows)

        # Fetch results
        results = query.all()

        # Process results to handle date and time objects
        data = []
        for row in results:
            row_data = {}
            for column in table_model.__table__.columns:
                value = getattr(row, column.name)
                if value is not None:  # Ensure value is not None
                    if isinstance(value, datetime.date):  # Check for date objects
                        row_data[column.name] = value.strftime("%Y-%m-%d")
                    elif isinstance(value, datetime.time):  # Check for time objects
                        row_data[column.name] = value.strftime("%H:%M:%S")
                    else:
                        row_data[column.name] = value
                else:
                    row_data[column.name] = None  # Handle None values
            data.append(row_data)

        # Prepare response
        response = {
            "page": page,
            "total": (total_records + rows - 1) // rows,  # Total pages
            "records": total_records,
            "rows": data,
        }
        return jsonify(response)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

