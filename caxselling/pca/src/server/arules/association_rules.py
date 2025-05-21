# Database
from database.db_manager import DatabaseConnection

# Data Manipulation and Analysis
import numpy as np
import daal4py as d4p

# Modin
import os
os.environ["MODIN_CPUS"] = "4"
import modin.pandas as pd
import pickle

# Logging
import logging
logger = logging.getLogger(__name__)

from database.arules import Arule_sch

class ARDiscoverer():
    def __new__(cls):
        """Singleton pattern to ensure only one instance of ARDiscoverer exists."""
        if not hasattr(cls, 'instance'):
            cls.instance = super(ARDiscoverer, cls).__new__(cls)
        return cls.instance

    def __init__(self, min_support:float=0.001, min_confidence:float=0.7):
        if not hasattr(self, 'algoDiscoverer'):
            if min_support < 0 or min_support > 1:
                message = "[ARDiscoverer] Invalid min_support value. It must be between 0 and 1."
                logger.error(message)  
                raise ValueError(message)
            
            if min_confidence < 0 or min_confidence > 1:
                message = "[ARDiscoverer] Invalid min_confidence value. It must be between 0 and 1."
                logger.error(message)  
                raise ValueError(message)
            
            self.min_support = min_support
            self.min_confidence = min_confidence
            self.model = None
            
            self.algoDiscoverer = d4p.association_rules(
                discoverRules=True,
                minSupport=self.min_support,
                minConfidence=self.min_confidence
            )

            self.lastResult = None
            self.ntransactions = None
            self.__reloadAR() # Reload the Association Rules clients from the database

    def __reloadAR(self):
        connPG=None
        errorMessage=None
        try:
            connPG = DatabaseConnection.connect()
            if connPG is None:
                message = "[ARDiscoverer] Error connecting to the database."
                logger.error(message)  
                return False
            
            with connPG.cursor() as cursor:
                # Check if the table exists
                query = """
                    SELECT uuid, antecedentitemsets, consequentitemsets, confidence, largeitemsets, largeitemsetssupport, min_confidence, min_support, ntransactions
                    FROM public.arules
                    order by 1 desc 
                    limit 1
                """
                if cursor is None:
                    result = None
                else:
                    cursor.execute(query)
                    result = cursor.fetchone()
                                                
                if result is None:
                    errorMessage = "[ARDiscoverer] No data found in the arules table."
                    logger.error(errorMessage)  
                else:

                    self.min_confidence = result[6]
                    self.min_support = result[7]
                    self.ntransactions = result[8]

                    self.lastResult = ARDiscovererResult(
                        antecedentItemsets=pickle.loads(result[1]),
                        consequentItemsets=pickle.loads(result[2]),
                        confidence=pickle.loads(result[3]),
                        largeItemsets=pickle.loads(result[4]),
                        largeItemsetsSupport=pickle.loads(result[5]),
                        pconfidence=self.min_confidence,
                        psupport=self.min_support,
                        pntransactions=self.ntransactions)
                    
                    logger.error(f"[ARDiscoverer] {len(self.lastResult.myRulesID)} ARules reloaded from the database. MinConfidence: {self.min_confidence}, MinSupport: {self.min_support}")
        except Exception as e:
            errorMessage = f"[ARDiscoverer] (__reloadAR) Error connecting to the database: {str(e)}"
            logger.error(errorMessage)  
        finally:
            if connPG is not None:
                connPG.close()

        return errorMessage is None
    
    @staticmethod
    def get_items(ruleID, nparray):
        """
        Get the items from the ruleID.
        Args:
            ruleID (int): The ID of the rule.
            nparray (numpy.ndarray): The numpy array with the rules.
        Returns:
            list: The items in the rule.
        """
        try:
            filter_arr = nparray[:, 0] == ruleID

            return nparray[filter_arr,1] #return itemIDs
        except Exception as e:
            message = f"[ARDiscoverer] get_items: Error getting items from ruleID {ruleID}: {str(e)}"
            logger.error(message)  
            raise None

    
    def fitFromPostgres(self, tablename:str="PRODUCTSTRX", columns:list=["IDTRANSACTION", "IDPRODUCT"]):
        """
        Fit the model using data from a PostgreSQL database. Return the result of the association rule mining and store it in the database.
        Args:
            tablename (str): The name of the table in the database.
            columns (list): The columns to be used for the association rule mining. First column must be the transaction ID, second column must be the product ID.
        """
        #Verifies if the table exists
        if not DatabaseConnection.existTable(tablename):
            message = f"[ARDiscoverer] Table {tablename} does not exist in the database."
            logger.error(message)  
            raise ValueError(message)
        
        if not DatabaseConnection.existColumnsInTable(tablename, columns):
            message = f"[ARDiscoverer] Table {tablename} does not have the required columns {columns}."
            logger.error(message)  
            raise ValueError(message)
        
        # Get column names for query
        colnames = ", ".join(columns) #List of Comma-separated columns
        errorMessage=None
        resAR = None
        connPG = None
        df = None
        try:                   
            query = f"SELECT {colnames} FROM {tablename} order by 1 asc, 2 asc"
            
            df = pd.read_sql(query, DatabaseConnection.get_pg_connection_string())
            if df is None:
                errorMessage = f"[ARDiscoverer] The table {tablename} is empty."
                logger.error(errorMessage)
                return None
                        
            # Numpy Array as expected by DAAL
            logger.info(f"[ARDiscoverer] Dataframe shape: {df.shape}")
            dfnumpy = df.to_numpy()
            
            logger.info(f"[ARDiscoverer] Numpy-ready Dataframe. Starting the processing")
            resAR = self.algoDiscoverer.compute(dfnumpy)

            if resAR is None:
                errorMessage = "[ARDiscoverer] Empty Result."
                logger.error(errorMessage)
                return None
            else:
                """
                Reference: https://intelpython.github.io/daal4py/algorithms.html#daal4py.association_rules_result
                
                resAR.antecedentItemsets #NumpyArray
                resAR.confidence #NumpyArray
                resAR.consequentItemsets #NumpyArray
                resAR.largeItemsets #NumpyArray
                resAR.largeItemsetsSupport #NumpyArray
                """

                connPG = DatabaseConnection.connect()
                if connPG is None:
                    errorMessage = "[ARDiscoverer] Result was not persisted in PG."
                    logger.error(errorMessage)
                    
                    self.ntransactions = len(df)
                    self.lastResult = ARDiscovererResult(
                        antecedentItemsets=resAR.antecedentItemsets,
                        consequentItemsets=resAR.consequentItemsets,
                        confidence=resAR.confidence,
                        largeItemsets=resAR.largeItemsets,
                        largeItemsetsSupport=resAR.largeItemsetsSupport,
                        pconfidence=self.min_confidence,
                        psupport=self.min_support,
                        pntransactions=self.ntransactions)
                    return self.lastResult
                else:
                    self.ntransactions = len(df)
                    with connPG.cursor() as curs:
                        curs.execute("truncate table arules")

                        sql = """
                        INSERT INTO  arules (antecedentItemsets, consequentItemsets, confidence,largeItemsets,largeItemsetsSupport,min_confidence, min_support, ntransactions) 
                        values (%s, %s, %s,%s,%s,%s,%s,%s)
                        """
                        values = (pickle.dumps(resAR.antecedentItemsets),
                                  pickle.dumps(resAR.consequentItemsets),
                                  pickle.dumps(resAR.confidence),
                                  pickle.dumps(resAR.largeItemsets),
                                  pickle.dumps(resAR.largeItemsetsSupport),
                                  self.min_confidence,
                                  self.min_support,
                                  self.ntransactions)
                        curs.execute(sql, values)
                        connPG.commit()
        except Exception as e:
            errorMessage = f"[ARDiscoverer] Error connecting to the database: {str(e)}"
            logger.error(errorMessage)
        finally:
            if connPG is not None:
                connPG.close()

        if errorMessage is not None:
            logger.error(errorMessage)
            return None
        
        self.lastResult = ARDiscovererResult(
            antecedentItemsets=resAR.antecedentItemsets,
            consequentItemsets=resAR.consequentItemsets,
            confidence=resAR.confidence,
            largeItemsets=resAR.largeItemsets,
            largeItemsetsSupport=resAR.largeItemsetsSupport,
            pconfidence=self.min_confidence,
            psupport=self.min_support,
            pntransactions=self.ntransactions)

        return self.lastResult

    
class ARDiscovererResult():
    def __init__(self, antecedentItemsets, consequentItemsets, confidence, largeItemsets, largeItemsetsSupport,pconfidence=None,psupport=None,pntransactions=None):
        self.antecedentItemsets = antecedentItemsets
        self.consequentItemsets = consequentItemsets
        self.confidence = confidence
        self.largeItemsets = largeItemsets
        self.largeItemsetsSupport = largeItemsetsSupport
        
        self.min_confidence = pconfidence
        self.min_support = psupport
        self.ntransactions = pntransactions

        self.myRulesID = np.unique(self.antecedentItemsets[:, 0])
    
    def see_antecends(self, productID:int):
        """
        See the antecedent rules where the productID is a consequent.
        Args:
            productID (int): The ID of the product in the consequent.
        Returns:
            list: The antecedents of the product.
        """
        targetIDs = np.array([productID])
        unified={}
        
        for rID in self.myRulesID:
            if len(np.intersect1d(targetIDs,ARDiscoverer.get_items(rID, self.consequentItemsets)))>0:
                # This rule has the productID in the consequent
                for ant in ARDiscoverer.get_items(rID, self.antecedentItemsets):
                    if ant not in unified:
                        unified[ant] = 1
                    else:
                        unified[ant] += 1

        return [k for k, v in sorted(unified.items(), key=lambda item: item[1], reverse=True)]
    
        
    def see_consequents(self, productID:list):
        """
        See the consequent rules where the productID belongs to the antecedent.
        Args:
            productID (list): List of Product IDs in the antecedent.
        Returns:
            list: The consequents for the subset of ProductIDs in the  antecedent.
        """
        targetIDs = np.array(productID)
        unified={}
        
        for rID in self.myRulesID:
            if len(np.intersect1d(targetIDs,ARDiscoverer.get_items(rID, self.antecedentItemsets)))>0:
                # This rule has the productID in the antecedent
                for conseq in ARDiscoverer.get_items(rID, self.consequentItemsets):
                    if conseq not in unified:
                        unified[conseq] = 1
                    else:
                        unified[conseq] += 1

        return [k for k, v in sorted(unified.items(), key=lambda item: item[1], reverse=True)]

            
    def see_rules_someof(self, productID:list):
        """
        See the rules associated with any of the productID belongs to the antecedent/consequent. When a rule contains at least one of the productID, it is returned.
        Args:
            productID (list): List of Product IDs in the antecedent.
        Returns:
            list: The consequents for the subset of ProductIDs in the  antecedent.
        """
        targetIDs = np.array(productID)
        unified={}

        for rID in self.myRulesID:
            if len(np.intersect1d(targetIDs,ARDiscoverer.get_items(rID, self.antecedentItemsets)))>0 or len(np.intersect1d(targetIDs,ARDiscoverer.get_items(rID, self.consequentItemsets)))>0:
                # This rule has the productID in the antecedent or consequent
                if rID not in unified:
                    item=Arule_sch()
                    errorMessage=None
                    try:
                        pants = ARDiscoverer.get_items(rID, self.antecedentItemsets)
                        if pants is not None and len(pants) > 0:
                            item.antecedents = [int(x) for x in pants]
                        else:
                            item.antecedents = []

                        pcons = ARDiscoverer.get_items(rID, self.consequentItemsets)
                        if pcons is not None and len(pcons) > 0:
                            item.consequents = [int(x) for x in pcons]
                        else:
                            item.consequents = None
                                               
                        sconf=self.confidence[rID]
                        if sconf is not None and len(sconf) > 0:
                            item.confidence = float(sconf[-1])
                        else:
                            item.confidence = None
                        
                        slarge=self.largeItemsetsSupport[rID]
                        if slarge is not None and len(slarge) > 0:
                            item.support = int(slarge[-1]) #It returns 1D array with 2 positions [# rule and #transactions supporting the rule]
                        else:
                            item.support = None
                        
                        item.ntransactions = int(self.ntransactions)
                        
                        unified[rID] = item
                    except Exception as e:
                        errorMessage = f"[ARDiscoverer] see_rules: Error getting items from ruleID {rID}: {str(e)}"
                        logger.error(errorMessage)  
                                                

        return sorted(unified.values(), key=lambda item: (item.support if item.support is not None else 0), reverse=True)

    def see_rules_strict(self, productID:list, pantecedent:bool=True):
        """
        See the rules associated with all productIDs belonging to the antecedent (pantecedent=TRUE) / consequent (pantecedent=FALSE).
        Args:
            productID (list): List of Product IDs in the antecedent.
        Returns:
            list: The consequents for the subset of ProductIDs in the  antecedent.
        """
        targetIDs = np.array(productID)
        target_len = len(targetIDs)
        unified={}

        for rID in self.myRulesID:
            ruleID=None
            if pantecedent:
                #Antecedent
                if len(np.intersect1d(targetIDs,ARDiscoverer.get_items(rID, self.antecedentItemsets))) == target_len:
                    # This rule has all inidcated productIDs in the antecedent
                    ruleID = rID                
            else:
                #Consequent
                if  len(np.intersect1d(targetIDs,ARDiscoverer.get_items(rID, self.consequentItemsets))) == target_len:
                    # This rule has all inidcated productIDs in the consequent
                    ruleID = rID
            
            if ruleID is not None:
                # This rule has all productIDs in the (antecedent or consequent) based on pantecedent
                if rID not in unified:
                    item=Arule_sch()
                    errorMessage=None
                    try:
                        pants = ARDiscoverer.get_items(rID, self.antecedentItemsets)
                        if pants is not None and len(pants) > 0:
                            item.antecedents = [int(x) for x in pants]
                        else:
                            item.antecedents = []

                        pcons = ARDiscoverer.get_items(rID, self.consequentItemsets)
                        if pcons is not None and len(pcons) > 0:
                            item.consequents = [int(x) for x in pcons]
                        else:
                            item.consequents = None
                                               
                        sconf=self.confidence[rID]
                        if sconf is not None and len(sconf) > 0:
                            item.confidence = float(sconf[-1])
                        else:
                            item.confidence = None
                        
                        slarge=self.largeItemsetsSupport[rID]
                        if slarge is not None and len(slarge) > 0:
                            item.support = int(slarge[-1]) #It returns 1D array with 2 positions [# rule and #transactions supporting the rule]
                        else:
                            item.support = None
                        
                        item.ntransactions = int(self.ntransactions)
                        
                        unified[rID] = item
                    except Exception as e:
                        errorMessage = f"[ARDiscoverer] see_rules: Error getting items from ruleID {rID}: {str(e)}"
                        logger.error(errorMessage)  
                                                
        return sorted(unified.values(), key=lambda item: (item.support if item.support is not None else 0), reverse=True)



