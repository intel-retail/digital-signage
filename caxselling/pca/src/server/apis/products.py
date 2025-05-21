import os
#Flask API
from flask_restx import Namespace, Resource, fields
#PostgresSQL & MQTT
from database.db_manager import DatabaseConnection
#Logging
import logging
logger = logging.getLogger(__name__)

api = Namespace('PCA - Products', description='Operations related to Products (Definition and transactions)')

## Schemas
product_sch = api.model('Product', {
    'idproduct': fields.Integer(required=True,  default=None, description="ID Product.",  example="1050"),
    'pname': fields.String(required=True, default=None, description="Short product name",  example="Banana"),
    'pdescription': fields.String(required=False, default=None, description="Product Descriptive characterization.",  example="Tasted and sweet banana grown in Ecuador."),                         
    'price': fields.Float(required=False,  default=None, description="Reference price for the product expressed in the sale unit.", example="0.5"),                        
})

class Product_sch(object):
    idproduct:int=None
    pname:str=None
    pdescription:str=None
    price:float=None

# Define the model for a list of products
products_list_sch = api.model('ProductsList', {
    'products': fields.List(fields.Nested(product_sch), required=True, description="List of products", 
         example="""
            [
                {
                "idproduct": 1050,
                "pname": "Banana",
                "pdescription": "Tasted and sweet banana grown in Ecuador.",
                "price": 0.5
                },
                {
                "idproduct": 1051,
                "pname": "Apple",
                "pdescription": "Red apple from Chile.",
                "price": 0.7
                }
            ]
        """),
})

producttrx_sch = api.model('ProductTrx', {
    'idtransaction': fields.Integer(required=True, default=None, description="ID Transaction",example="587469"),
    'idproduct': fields.Integer(required=True, default=None, description="ID Product", example="1050"),
    'quantity': fields.Integer(required=True, default=None, description="Quanty of the product sold in this transaction",  example="1"),
    'unitaryprice': fields.Float(required=False, default=None, description="Product Unitary Price in this transaction",  example="0.57")
})

# Define the model for a list of products
productstrx_list_sch = api.model('ProductsTrxList', {
    'transactions': fields.List(fields.Nested(producttrx_sch), required=True, description="List of product transactions",
            example="""
                [
                    {
                    "idtransaction": 587469,
                    "idproduct": 1050,
                    "quantity": 2,
                    "unitaryprice": 0.57
                    },
                    {
                    "idtransaction": 587469,
                    "idproduct": 1051,
                    "quantity": 1,
                    "unitaryprice": 0.70
                    }
                ]
            """)
})

class Producttrx_sch(object):
    idtransaction:int=None
    idproduct:int=None
    quantity:int=None
    unitaryprice:float=None

## Products API
@api.route('/prd/',
           doc={"description":"Operations related to Products (Definition and transactions)"})
class Products(Resource):
    @api.response(200, 'Success')
    @api.response(204, 'No Products to register')
    @api.response(500, 'Accepted but it could not be processed/stored')
    @api.expect(products_list_sch, validate=True, description="List of products to register")
    def post(self):
        data = api.payload # data['products'] will be a list of product dicts
        products = data.get('products')
        if len(products) == 0:
            message = "No products to register"
            logger.error(message)
            return message, 204

        conn = None
        errorMessage=None
        try:
            conn = DatabaseConnection.connect()            
            if conn is None:                
                message=f"PG Connection Error"
                logger.error(message)
                return message, 500
                        
            with conn.cursor() as curs:
                for product in products:
                    curs.execute(f"SELECT idproduct from products where idproduct={product.get('idproduct')};")
                    results = curs.fetchall()
                    if len(results)>0:
                        # UPDATE
                            myinsert = """
                              UPDATE public.products
	                            SET pname=%s, pdescription=%s, price=%s
	                            WHERE idproduct=%s;
                                
                            """
                            values = (
                                product.get('pname'),
                                product.get('pdescription'),
                                product.get('price') if product.get('price') is not None else None,
                                product.get('idproduct')
                            )
                            curs.execute(myinsert, values)
                    else:
                        # INSERT
                            myinsert = """
                              INSERT INTO public.products(
	                            idproduct, pname, pdescription, price)
	                            VALUES (%s, %s, %s, %s);
                                
                            """
                            values = (
                                product.get('idproduct'),
                                product.get('pname'),
                                product.get('pdescription'),
                                product.get('price') if product.get('price') is not None else None
                            )
                            curs.execute(myinsert, values)

            conn.commit() # Confirm the deletion
                
        except Exception as e:
            conn.rollback()
            errorMessage=f"Products Registration Error (Rollback): {str(e)}"
            logger.error(errorMessage)
        finally:
            if conn is not None:
                conn.close()
                
        if errorMessage is not None:
            return errorMessage, 500
        
        return "Success", 200
    
    @api.response(200, 'Success')
    @api.response(204, 'No Products to delete')
    @api.response(500, 'Accepted but it could not be processed/stored')
    @api.expect(products_list_sch, validate=True, description="List of products to delete")
    def delete(self):
        data = api.payload # data['products'] will be a list of product dicts
        products = data.get('products')
        if len(products) == 0:
            message = "No products to delete"
            logger.error(message)
            return message, 204

        conn = None
        errorMessage=None
        try:
            conn = DatabaseConnection.connect()            
            if conn is None:                
                message=f"PG Connection Error"
                logger.error(message)
                return message, 500
                        
            with conn.cursor() as curs:
                for product in products:
                    # UPDATE
                    mydelete = """
                        DELETE FROM public.products
                        WHERE idproduct=%s;                        
                    """
                    values = (
                        product.get('idproduct'),
                    )
                    curs.execute(mydelete, values)

            conn.commit() # Confirm the deletion                
        except Exception as e:
            conn.rollback()
            errorMessage=f"Products Delete Error (Rollback): {str(e)}"
            logger.error(errorMessage)
        finally:
            if conn is not None:
                conn.close()
        
        if errorMessage is not None:
            return errorMessage, 500
        
        return "Success", 200

## Products API
@api.route('/prd/<string:filtername>', 
           doc={"description":"Get a list of products that match a filter for the product name (Limited to 50)"})
@api.param('filtername', 'Filter for the product name')
class ProductsQuery(Resource):
    @api.response(200, 'Success')
    @api.response(404, 'No Products found')
    @api.response(500, 'Accepted but it could not be processed/stored')
    @api.marshal_list_with(product_sch)
    def get(self,filtername):
        #To Do
        list=[]
        conn = None
        errorMessage=None
        try:
            conn = DatabaseConnection.connect()            
            if conn is None:
                message=f"PG Connection Error"
                logger.error(message)
                return list, 500
                       
            with conn.cursor() as curs:
                curs.execute(f"SELECT idproduct, pname, pdescription, price FROM public.products where lower(pname) like '%{filtername.lower()}%' order by pname limit 50;")
                results = curs.fetchall()

                while results:
                    row = results.pop(0)
                    data=Product_sch()
                    data.idproduct=int(row[0])
                    data.pname=str(row[1])
                    if row[2] is None:
                        data.pdescription=None
                    else:
                        data.pdescription=str(row[2])
                    if row[3] is None:
                        data.price=None
                    else:
                        data.price=float(row[3])                   
                    
                    list.append(data)

        except Exception as e:
            errorMessage=f"Query products based on the filter: ({filtername})   Error: {str(e)}"
            logger.error(errorMessage)            
        finally:
            if conn is not None:
                conn.close()

        if errorMessage is not None:
            return list, 500
        
        if len(list)==0:
            return list, 404
                
        return list, 200

###ACA
## Products API
@api.route('/prd/trx/', 
           doc={"description":"Operations related to Product Transactions"})
class ProductTrx(Resource):
    @api.response(200, 'Success')
    @api.response(204, 'No transactions to register')
    @api.response(500, 'Accepted but it could not be processed/stored')
    @api.expect(productstrx_list_sch, validate=True, description="List of product transactions to register")
    def post(self):
        data = api.payload # data['transactions'] will be a list of product dicts
        transactions = data.get('transactions')
        if len(transactions) == 0:
            message = "No transactions to register"
            logger.error(message)
            return message, 204

        conn = None
        errorMessage=None
        try:
            conn = DatabaseConnection.connect()            
            if conn is None:                
                message=f"PG Connection Error"
                logger.error(message)
                return message, 500
                        
            with conn.cursor() as curs:
                for transaction in transactions:
                    curs.execute(f"SELECT 1 from productstrx where idtransaction={transaction.get('idtransaction')} and idproduct={transaction.get('idproduct')};")
                    results = curs.fetchall()
                    if len(results)>0:
                        # UPDATE
                            myinsert = """
                              UPDATE public.productstrx
	                            SET quantity=%s, unitaryprice=%s
	                            WHERE idproduct=%s and idtransaction=%s;                                
                            """
                            values = (
                                transaction.get('quantity') if transaction.get('quantity') is not None else None,
                                transaction.get('unitaryprice') if transaction.get('unitaryprice') is not None else None,
                                transaction.get('idproduct'),
                                transaction.get('idtransaction')
                            )
                            curs.execute(myinsert, values)
                    else:
                        # INSERT
                            myinsert = """
                                INSERT INTO public.productstrx(
                                    idtransaction, idproduct, quantity, unitaryprice)
                                    VALUES (%s, %s, %s, %s);                                
                            """
                            values = (
                                transaction.get('idtransaction'),
                                transaction.get('idproduct'),
                                transaction.get('quantity') if transaction.get('quantity') is not None else None,
                                transaction.get('unitaryprice') if transaction.get('unitaryprice') is not None else None
                            )
                            curs.execute(myinsert, values)

            conn.commit() # Confirm the deletion
                
        except Exception as e:
            conn.rollback()
            errorMessage=f"Products Registration Error (Rollback): {str(e)}"
            logger.error(errorMessage)

        finally:
            if conn is not None:
                conn.close()

        if errorMessage is not None:
            return errorMessage, 500
                        
        return "Success", 200
    
    @api.response(200, 'Success')
    @api.response(204, 'No Product transactions to delete')
    @api.response(500, 'Accepted but it could not be processed/stored')
    @api.expect(productstrx_list_sch, validate=True, description="List of product transactions to delete")
    def delete(self):
        data = api.payload # data['products'] will be a list of product dicts
        transactions = data.get('transactions')
        if len(transactions) == 0:
            message = "No transactions to delete"
            logger.error(message)
            return message, 204

        conn = None
        errorMessage=None
        try:
            conn = DatabaseConnection.connect()            
            if conn is None:                
                message=f"PG Connection Error"
                logger.error(message)
                return message, 500
                        
            with conn.cursor() as curs:
                for transaction in transactions:
                    # UPDATE
                    mydelete = """
                        DELETE FROM public.productstrx
                        WHERE idtransaction=%s and idproduct=%s;                        
                    """
                    values = (
                        transaction.get('idtransaction'),
                        transaction.get('idproduct')
                    )
                    curs.execute(mydelete, values)

            conn.commit() # Confirm the deletion                
        except Exception as e:
            conn.rollback()
            errorMessage=f"Product Transactions Delete Error (Rollback): {str(e)}"
            logger.error(errorMessage)
            
        finally:
            if conn is not None:
                conn.close()

        if errorMessage is not None:
            return errorMessage, 500
            
        return "Success", 200

## Product Transactions API
@api.route('/prd/<int:idtrx>', 
           doc={"description":"Get a list of products that match a filter for the idtransaction (Limited to 50)"})
@api.param('idtrx', 'IDtransaction to get the items')
class ProductTrxQuery(Resource):
    @api.response(200, 'Success')
    @api.response(404, 'No Products found')
    @api.response(500, 'Accepted but it could not be processed/stored')
    @api.marshal_list_with(producttrx_sch)
    def get(self,idtrx):
        #To Do
        list=[]
        conn = None
        errorMessage=None
        try:
            conn = DatabaseConnection.connect()            
            if conn is None:
                message=f"PG Connection Error"
                logger.error(message)
                return list, 500
                       
            with conn.cursor() as curs:
                curs.execute(f"SELECT idproduct,quantity,unitaryprice from productstrx where idtransaction={idtrx} limit 50;")
                results = curs.fetchall()

                while results:
                    row = results.pop(0)
                    data=Producttrx_sch()
                    data.idtransaction=int(idtrx)
                    data.idproduct=int(row[0])
                    if row[1] is None:
                        data.quantity=None
                    else:
                        data.quantity=str(row[1])
                    if row[2] is None:
                        data.unitaryprice=None
                    else:
                        data.unitaryprice=float(row[2])                   
                    
                    list.append(data)

        except Exception as e:
            errorMessage=f"Query products based on the filter: ({idtrx})   Error: {str(e)}"
            logger.error(errorMessage)
            
        finally:
            if conn is not None:
                conn.close()

        if errorMessage is not None:
            return list, 500
        
        if len(list)==0:
            return list, 404
                
        return list, 200
