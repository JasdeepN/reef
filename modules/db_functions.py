from sqlalchemy import insert 
from sqlalchemy import select, update, delete
from app import db

# Create
async def create_row(table_class, data):
    try:
        stmt = insert(table_class).values(data)
        result = db.session.execute(stmt)
        db.session.commit()
        return result.inserted_primary_key
    except Exception as e:
        print(f"Error creating row: {e}")
        db.session.rollback()
        return None

# Read
async def read_rows(table_class, filters=None):
    try:
        stmt = select(table_class)
        if filters:
            stmt = stmt.filter_by(**filters)
        result = db.session.execute(stmt).scalars().all()
        return result
    except Exception as e:
        print(f"Error reading rows: {e}")
        return None

# Update
async def update_row(table_class, filters, update_data):
    try:
        stmt = update(table_class).where(*[getattr(table_class, k) == v for k, v in filters.items()]).values(update_data)
        db.session.execute(stmt)
        db.session.commit()
        return True
    except Exception as e:
        print(f"Error updating row: {e}")
        db.session.rollback()
        return False

# Delete
async def delete_row(table_class, filters):
    try:
        stmt = delete(table_class).where(*[getattr(table_class, k) == v for k, v in filters.items()])
        db.session.execute(stmt)
        db.session.commit()
        return True
    except Exception as e:
        print(f"Error deleting row: {e}")
        db.session.rollback()
        return False

# Test functions
async def insert_test_row(table_class, data):  
  clean_data = await process_data(data)
  assert clean_data != {}, "no data to insert"
  try:
    print('try this data', clean_data)
    stmt = insert(table_class).values(clean_data)
    print(stmt)
    compiled = stmt.compile()
    print(compiled.params) 
  except Exception as err:
    print(f"Unexpected {err=}, {type(err)=}")
    raise
    print('error compiling insert statment')
    return False

  try:
    result = db.session.execute(stmt)
    db.session.commit()
    return True
  except:
    print('error executing sql')

async def process_data(dirty):
  # print('process', dirty)
  clean_data = {}
  if dirty.po4_ppb.data != None:
    dirty.po4_ppm.data = (3.066*float(dirty.po4_ppb.data)/1000)
    # print("PPB TO PPM CONVERSION COMPLETE", dirty.data['po4_ppm'],  3.066*int(dirty.data['po4_ppb'])/1000)

  try:
    for row in dirty:  
      # print(row)
      if (row.id != 'csrf_token' and row.id != 'submit'):
          print('check', row.id,  row.data)
          
          if row.data is not None:
            # print(row.data)
            clean_data.update({row.id: row.data})
   
    print('cleaned', clean_data)   
    return clean_data
  except:
    print('error cleaning data')
    print(clean_data)

    return {}
  
async def get_test_row(table_class, id):
  try:
    stmt = select(table_class).where(table_class.id == id)
    result = db.session.execute(stmt)
    row = result.fetchone()
    if row:
      return row
    else:
      return None
  except Exception as err:
    print(f"Unexpected {err=}, {type(err)=}")
    raise
    print('error getting test row')
    return None
