from django.shortcuts import render
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
import json
import os
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
import html
from bs4 import BeautifulSoup

class Process(APIView):
    
    #used to fetch experian score 
    def getExperianScore(self, experianSoup):
        score = None
        try:
            # print(experianSoup)
            score = experianSoup.find('SCORE').find('BureauScore').get_text().strip()
        except Exception as e:
            print(e)
        
        return score
    
    #used to fetch experian score 
    def getCrifScore(self, crifSoup):
        score = None
        try:
            # print(experianSoup)
            score = crifSoup.find('SCORES').find('SCORE').find('SCORE-VALUE').get_text().strip()
        except Exception as e:
            print(e)
        
        return score
    
    def post(self, request):
        # print(request.data)
        redReasons = set() #stores all rejection reasons
        greenReasons = set() #stores all acceptance reasons
        amberReasons = set() #stores all amber case reasons
        crifData = None #holds crif file data
        experianData = None #holds experian file data
        channel = -1 #staus of user i.e. Green = 1, Amber = 2 or Red = 3

        #saving memory loaded experian file for further processing
        #START
        try:
            tmp = os.path.join(settings.MEDIA_ROOT, "tmp", request.data['experian'].name)
            path = default_storage.save(tmp, ContentFile(request.data['experian'].read()))
            file = os.path.join(settings.MEDIA_ROOT, path)

            #loading json file 
            f = open(file)
            experianData = json.load(f)
            f.close()
            os.remove(file)
        except Exception as e:
            print(e)
            # notes.append("Experian file not available or not provided in proper format")
            return Response(data={"error": "Experian file not found or not in proper format", 'status': "","totalReasons":0, 'reasons': [], "amberReaons": [], "delinquencies":{"EXPERIAN":{}, "CRIF":{}}}, status = status.HTTP_406_NOT_ACCEPTABLE) 
        #END


        #saving memory loaded CRIF file for further processing
        #START
        try:
            tmp = os.path.join(settings.MEDIA_ROOT, "tmp", request.data['crif'].name)
            path = default_storage.save(tmp, ContentFile(request.data['crif'].read()))
            file = os.path.join(settings.MEDIA_ROOT, path)

            #loading json file 
            f = open(file)
            crifData = json.load(f)
            f.close()
            os.remove(file)
        except Exception as e:
            print(e)
            # notes.append("CRIF file not available or not provided in proper format")
            return Response(data={"error": "CRIF file not found or not in proper format", 'status': "","totalReasons":0, 'reasons': [], "amberReaons": [], "delinquencies":{"EXPERIAN":{}, "CRIF":{}}}, status = status.HTTP_406_NOT_ACCEPTABLE) 
        #END


        if (not crifData) and (not experianData):
            return Response(data={"error": "CRIF and Experian file not found or not in proper format", 'status': "", "totalReasons":0, 'reasons': [], "amberReaons": [], "delinquencies":{"EXPERIAN":{}, "CRIF":{}}}, status = status.HTTP_406_NOT_ACCEPTABLE) 

        experianHTML = ''
        if(experianData):
            try:
                experianHTML = experianData["experianProviderResponse"]["showHtmlReportForCreditReport"]
                experianHTML = html.unescape(experianHTML)
                # print(experianHTML)
            except Exception as e:
                print(e)
                return Response(data={"error": "Experian file not found or not in proper format", 'status': "", "totalReasons":0, 'reasons': [], "amberReaons": [], "delinquencies":{"EXPERIAN":{}, "CRIF":{}}}, status = status.HTTP_406_NOT_ACCEPTABLE) 

        else:
            pass
        
         #Experian processing
        try:
            experianSoup = BeautifulSoup(experianHTML, 'xml')
            experianSoup = experianSoup.find('INProfileResponse')
        except Exception as e:
            print(e)
            return Response(data={"error": "Experian file not found or not in proper format", 'status': "", "totalReasons":0, 'reasons': [], "amberReaons": [], "delinquencies":{"EXPERIAN":{}, "CRIF":{}}}, status = status.HTTP_406_NOT_ACCEPTABLE) 
        
        experianScore = self.getExperianScore(experianSoup)
        # print(experianScore)
        if(experianScore):
            # print(experianScore)
            experianScore = float(experianScore)
            if experianScore < 600:
                channel = 3
                redReasons.add("Experian score below 600")
            elif experianScore >=600 and experianScore <=700:
                channel = 2
                amberReasons.add("Experian score is in 600 to 700 range")
            elif experianScore > 700:
                channel = 1
                greenReasons.add("Experian score is more than 700")
        else:
            amberReasons.add("Experian Score not available")
            channel = 2
        #END
        

        crifHTML = None
        if(crifData):
            try:
                crifHTML = crifData["crifProviderResponse"]["crifCreditReport"]
                crifHTML = html.unescape(crifHTML)
                # print(crifHTML)
            except Exception as e:
                print(e)
                return Response(data={"error": "CRIF file not found or not in proper format", 'status': "", "totalReasons":0, 'reasons': "", "delinquencies":{"EXPERIAN":{}, "CRIF":{}}}, status = status.HTTP_406_NOT_ACCEPTABLE) 

        else:
            pass
        

        #CRIF processing
        try:
            crifSoup = BeautifulSoup(crifHTML, 'xml')
            crifSoup = crifSoup.find('B2C-REPORT')
        except Exception as e:
            print(e)
            return Response(data={"error": "CRIF file not found or not in proper format", 'status': "", "totalReasons":0, 'reasons': [], "amberReaons": [], "delinquencies":{"EXPERIAN":{}, "CRIF":{}}}, status = status.HTTP_406_NOT_ACCEPTABLE) 

        crifScore = self.getCrifScore(crifSoup)
        # print(crifScore)
        if(crifScore):
            # print(crifScore)
            crifScore = float(crifScore)
            if crifScore < 600:
                channel = 3
                redReasons.add("CRIF score below 600")
            elif crifScore >= 600 and crifScore < 650:
                if channel != 3:
                    channel = 2
                amberReasons.add("CRIF score in between 600 to 650")
            elif crifScore >= 650:
                if(channel <=1):
                    channel = 1
                    greenReasons.add("CRIF score is more than 650")
        else:
            amberReasons.add("CRIF Score not available")
            channel = 2
        
        #checking delinquency
        experianDict = []
        try:
            cias_accounts = experianSoup.find('CAIS_Account').findAll('CAIS_Account_DETAILS')
            # print(cias_accounts)
            for accnt in cias_accounts:
                dictFlag = True
                try:
                    # print("yes")
                    amount_past_due = accnt.find('Amount_Past_Due').get_text().strip()
                    if(amount_past_due):
                        amount_past_due = float(amount_past_due)
                    else:
                        amount_past_due = 0
                    # print(amount_past_due)

                    accntType = ""
                    try:
                        accntType =  accnt.find('Account_Type').get_text().strip()
                    except Exception as e:
                        print(e)
                    # print(accntType)

                    subName = ""
                    try:
                        subName =  accnt.find('Subscriber_Name').get_text().strip()
                    except Exception as e:
                        print(e)
                    # print(subName)

                    amntFinanced = ""
                    try:
                        amntFifnanced = experianSoup.find('Current_Application').find('Current_Application_Details').find('Amount_Financed').get_text().strip()
                    except Exception as e:
                        print(e)
                    # print(amntFinanced)

                    sfwf = ""
                    try:
                        sfwf =  accnt.find('SuitFiledWillfulDefaultWrittenOffStatus').get_text().strip()
                    except Exception as e:
                        print(e)
                    # print(sfwf)

                    acntHolderType = ""
                    try:
                        acntHolderType =  accnt.find('AccountHoldertypeCode').get_text().strip()
                    except Exception as e:
                        print(e)
                    # print(acntHolderType)

                    acntStatus = ""
                    try:
                        acntStatus =  accnt.find('Account_Status').get_text().strip()
                    except Exception as e:
                        print(e)
                    # print(acntStatus)
                    
                    if (amount_past_due > 1000 and accntType != '10') or (accntType=="10" and amount_past_due >=10000):
                        channel = 3
                        if accntType != '10':
                            redReasons.add("For Experian: Account type is not credit card and amount past due is greater than 1000")
                        else:
                            redReasons.add("For Experian: Account type is credit card and amount past due is greater than 10000")
                        
                        expDict = {"AmountPastDue": amount_past_due, "SubscriberName":subName, "AmountFinanced":amntFinanced, "AccountType":accntType, "SuitFiledWillfulDefaultWrittenOffStatus":sfwf, "AccountHolderType":acntHolderType, "AccountStatus":acntStatus}
                        if dictFlag:
                            experianDict.append(expDict)
                            dictFlag = False
                        
                        # break                 
                    elif ((accntType == '10' and amount_past_due<=10000) or (accntType != '10' and amount_past_due==0)):
                        if channel <=1:
                            channel = 1
                        if accntType == '10':
                            greenReasons.add("For Experian: Account type is 10 and amount past due is less than equal to 10000")
                        else:
                            greenReasons.add("For Experian: Account type is not equal to 10 and amount past due is 0 or not found")
                    else:
                        if channel != 3:
                            channel = 2
                        amberReasons.add("For Experian: Account type and amount past due lies in given constraints")
                        expDict = {"AmountPastDue": amount_past_due, "SubscriberName":subName, "AmountFinanced":amntFinanced, "AccountType":accntType, "SuitFiledWillfulDefaultWrittenOffStatus":sfwf, "AccountHolderType":acntHolderType, "AccountStatus":acntStatus}

                        if dictFlag:
                            dictFlag = False
                            experianDict.append(expDict)    
                    try:
                        accnt_history = accnt.findAll("CAIS_Account_History")
                        for history in accnt_history:
                            asset_classification = None
                            try:
                                asset_classification = history.find("Asset_Classification").get_text().strip()
                            except Exception as e:
                                print("asset_classification not found")
                                if channel != 3 and amberFlagA:
                                    channel = 2
                                amberReasons.add("For Experian: asset_classification not available")
                                expDict = {"AmountPastDue": amount_past_due, "SubscriberName":subName, "AmountFinanced":amntFinanced, "AccountType":accntType, "SuitFiledWillfulDefaultWrittenOffStatus":sfwf, "AccountHolderType":acntHolderType, "AccountStatus": acntStatus}

                                if dictFlag:
                                    dictFlag = False
                                    experianDict.append(expDict)

                            dpd = None
                            try:
                                dpd = history.find("Days_Past_Due").get_text().strip()
                            except Exception as e:
                                print("days past due not found")
                                if channel != 3:
                                    channel = 2 
                            
                            if dpd != None and int(dpd) >= 90:
                                channel = 3
                                redReasons.add("For Experian: DPD more than 90 days")
                                expDict = {"AmountPastDue": amount_past_due, "SubscriberName":subName, "AmountFinanced":amntFinanced, "AccountType":accntType, "SuitFiledWillfulDefaultWrittenOffStatus":sfwf, "AccountHolderType":acntHolderType, "AccountStatus": acntStatus}

                                if dictFlag:
                                    dictFlag = False
                                    experianDict.append(expDict)

                            if asset_classification == "B" or asset_classification == "D" or asset_classification == "M" or asset_classification == "L" :
                                channel = 3
                                redReasons.add("For Experian: Case of wilful default, written off, suit filed  in any of the loans")
                                expDict = {"AmountPastDue": amount_past_due, "SubscriberName":subName, "AmountFinanced":amntFinanced, "AccountType":accntType, "SuitFiledWillfulDefaultWrittenOffStatus":sfwf, "AccountHolderType":acntHolderType, "AccountStatus":acntStatus}
                                if dictFlag:
                                    dictFlag = False
                                    experianDict.append(expDict)
                            elif asset_classification != None:
                                if channel <=1:
                                    channel = 1
                                    greenReasons.add("For Experian: No written-off, willful default, Substandard, Doubtful, Special mention account and loss and settled status of loan")
                            else:
                                if channel != 3:
                                    channel = 2
                                amberReasons.add("For Experian: Assessts classification not found")
                                expDict = {"AmountPastDue": amount_past_due, "SubscriberName":subName, "AmountFinanced":amntFinanced, "AccountType":accntType, "SuitFiledWillfulDefaultWrittenOffStatus":sfwf, "AccountHolderType":acntHolderType, "AccountStatus": acntStatus}

                                if dictFlag:
                                    dictFlag = False
                                    experianDict.append(expDict)
                    except Exception as e:
                        print(e)
                        # print("Account history not found")
                        # if channel != 3:
                        #     channel = 2
                        # amberReasons.add("For Experian: Account history not available")
                except Exception as e:
                    print(e)
                    # print("Amount past due not found")
                    # if channel != 3:
                    #     channel = 2
                    # amberReasons.add("For Experian: Amount past due amount not available")
        except Exception as e:
            print(e)
            if channel <=1:
                channel = 1
                greenReasons.add("For Experian: deliquencies details not found")

        
        crifDict = []
        try:
            crifResponses = crifSoup.find('RESPONSES').findAll('RESPONSE')
            # print(crifResponses)

            for loans in crifResponses:
                dictFlag = True
                try:
                    overdueAmount = loans.find('LOAN-DETAILS').find('OVERDUE-AMT').get_text().strip()
                    if(overdueAmount):
                        overdueAmount = float(overdueAmount)
                    else:
                        overdueAmount = 0
                    # print(overdueAmount)

                    accntType = ""
                    try:
                        accntType = loans.find('LOAN-DETAILS').find('ACCT-TYPE').get_text().strip()
                        accntType = accntType.lower()
                    except Exception as e:
                        print(e)
                    # print(accntType)
                    
                    creditGrntr = ""
                    try:
                        creditGrntr = loans.find('LOAN-DETAILS').find('CREDIT-GUARANTOR').get_text().strip()
                    except Exception as e:
                        print(e)
                    # print(creditGrntr)

                    disbursedAmnt = ""
                    try:
                        disbursedAmnt = loans.find('LOAN-DETAILS').find('DISBURSED-AMT').get_text().strip()
                    except Exception as e:
                        print(e)
                    # print(disbursedAmnt)
                    
                    writeOffAmnt = ""
                    try:
                        writeOffAmnt = loans.find('LOAN-DETAILS').find('WRITE-OFF-AMT').get_text().strip()
                    except Exception as e:
                        print(e)
                    
                    ownershipInd = ""
                    try:
                        ownershipInd = loans.find('LOAN-DETAILS').find('OWNERSHIP-IND').get_text().strip()
                    except Exception as e:
                        print(e)
                    # print(ownershipInd)
                    
                    acntStatus = ""
                    try:
                        acntStatus = loans.find('LOAN-DETAILS').find('ACCOUNT-STATUS').get_text().strip()
                    except Exception as e:
                        print(e)
                    # print(acntStatus)

                    acntStatus = acntStatus.lower()
                    if (acntStatus == "substandard" or acntStatus == "doubtful" or acntStatus == "special mention account" or acntStatus == "loss" or acntStatus == "active"):
                        channel = 3
                        redReasons.add("For CRIF: Loan status is Substandard, Doubtful, Special mention account, loss, Active")
                        crDict = {"OverdueAmount": overdueAmount, "AccountType": accntType, "CreditGuarantor": creditGrntr, "DisbursedAmount": disbursedAmnt, "WriteOffAmount": writeOffAmnt, "OwnershipInd":ownershipInd, "AccountStatus": acntStatus}
                        
                        if dictFlag:
                            dictFlag = False
                            crifDict.append(crDict)
                    else:
                        if channel <= 1:
                            channel = 1
                            greenReasons.add("In CRIF: No Substandard, Doubtful, Special mention account and loss, Written-off,willful default and settled")


                    if (overdueAmount > 1000 and accntType != "credit card") or (accntType == 'credit card' and overdueAmount>10000):
                        channel = 3
                        if(accntType != "credit card"):
                            redReasons.add("For CRIF: Account Type is not creadit card and overdue amount is above 1000")
                        else:
                            redReasons.add("For CRIF: Account Type is creadit card and overdue amount is above 10000")
                        
                        crDict = {"OverdueAmount": overdueAmount, "AccountType": accntType, "CreditGuarantor": creditGrntr, "DisbursedAmount": disbursedAmnt, "WriteOffAmount": writeOffAmnt, "OwnershipInd":ownershipInd, "AccountStatus": acntStatus}
                        
                        if dictFlag:
                            dictFlag = False
                            crifDict.append(crDict)
                    elif (accntType == "credit card" and overdueAmount <= 10000) or (accntType != 'credit card' and overdueAmount == 0):
                        # print("green")
                        if channel <=1:
                            channel = 1
                            if accntType == "credit card":
                                greenReasons.add("For CRIF: Account type is credit card and overdueAmount less than equal to 10000")
                            else:
                                greenReasons.add("For CRIF: Account type is not credit card and overdueAmount is 0 or not found")
                    else:
                        if channel != 3:
                            channel = 2
                        amberReasons.add("For CRIF: Account type and overdueAmount not lies in given constraints")

                        crDict = {"OverdueAmount": overdueAmount, "AccountType": accntType, "CreditGuarantor": creditGrntr, "DisbursedAmount": disbursedAmnt, "WriteOffAmount": writeOffAmnt, "OwnershipInd":ownershipInd, "AccountStatus": acntStatus}
                        
                        if dictFlag:
                            dictFlag = False
                            crifDict.append(crDict)
                        
                except Exception as e:
                    print("overdue amount not found")
                    # if channel != 3:
                    #     channel = 2
                    # amberReasons.add("For CRIF: overdue amount not available")
                try:
                    linked_accnts = loans.find('LOAN-DETAILS').find("LINKED-ACCOUNTS").findAll("ACCOUNT-DETAILS")
                    for accnts in linked_accnts:
                        dictFlag = True
                        overdueAmount = 0
                        try:
                            overdueAmount = accnts.find('OVERDUE-AMT').get_text().strip()
                            if(overdueAmount):
                                overdueAmount = float(overdueAmount)
                        except Exception as e:
                            print(e)
                        # print(overdueAmount)

                        accntType = ""
                        try:
                            accntType = accnts.find('ACCT-TYPE').get_text().strip()
                            accntType = accntType.lower()
                        except Exception as e:
                            print(e)
                        # print(accntType)
                        
                        creditGrntr = ""
                        try:
                            creditGrntr = accnts.find('CREDIT-GUARANTOR').get_text().strip()
                        except Exception as e:
                            print(e)
                        # print(creditGrntr)

                        disbursedAmnt = ""
                        try:
                            disbursedAmnt = accnts.find('DISBURSED-AMT').get_text().strip()
                        except Exception as e:
                            print(e)
                        # print(disbursedAmnt)
                        
                        writeOffAmnt = ""
                        try:
                            writeOffAmnt = accnts.find('WRITE-OFF-AMT').get_text().strip()
                        except Exception as e:
                            print(e)
                        
                        ownershipInd = ""
                        try:
                            ownershipInd = accnts.find('OWNERSHIP-IND').get_text().strip()
                        except Exception as e:
                            print(e)
                        # print(ownershipInd)
                        
                        acntStatus = ""
                        try:
                            acntStatus = accnts.find('ACCOUNT-STATUS').get_text().strip()
                        except Exception as e:
                            print(e)
                        # print(acntStatus)

                        if (acntStatus == "substandard" or acntStatus == "doubtful" or acntStatus == "special mention account" or acntStatus == "loss" or acntStatus == "active"):
                            channel = 3
                            redReasons.add("For CRIF: Loan status is Substandard, Doubtful, Special mention account, loss, Active")
                            crDict = {"OverdueAmount": overdueAmount, "AccountType": accntType, "CreditGuarantor": creditGrntr, "DisbursedAmount": disbursedAmnt, "WriteOffAmount": writeOffAmnt, "OwnershipInd":ownershipInd, "AccountStatus": acntStatus}
                            
                            if dictFlag:
                                dictFlag = False
                                crifDict.append(crDict)
                        else:
                            if channel <= 1:
                                channel = 1
                                greenReasons.add("In CRIF: No Substandard, Doubtful, Special mention account and loss, Written-off,willful default and settled")


                        if (overdueAmount > 1000 and accntType != "credit card") or (accntType == 'credit card' and overdueAmount>10000):
                            channel = 3
                            if(accntType != "credit card"):
                                redReasons.add("For CRIF: Account Type is not creadit card and overdue amount is above 1000")
                            else:
                                redReasons.add("For CRIF: Account Type is creadit card and overdue amount is above 10000")
                            
                            crDict = {"OverdueAmount": overdueAmount, "AccountType": accntType, "CreditGuarantor": creditGrntr, "DisbursedAmount": disbursedAmnt, "WriteOffAmount": writeOffAmnt, "OwnershipInd":ownershipInd, "AccountStatus": acntStatus}
                            
                            if dictFlag:
                                dictFlag = False
                                crifDict.append(crDict)
                        elif (accntType == "credit card" and overdueAmount <= 10000) or (accntType != 'credit card' and overdueAmount == 0):
                            # print("green")
                            if channel <=1:
                                channel = 1
                                if accntType == "credit card":
                                    greenReasons.add("For CRIF: Account type is credit card and overdueAmount less than equal to 10000")
                                else:
                                    greenReasons.add("For CRIF: Account type is not credit card and overdueAmount is 0 or not found")
                        else:
                            if channel != 3:
                                channel = 2
                            amberReasons.add("For CRIF: Account type and overdueAmount not lies in given constraints")

                            crDict = {"OverdueAmount": overdueAmount, "AccountType": accntType, "CreditGuarantor": creditGrntr, "DisbursedAmount": disbursedAmnt, "WriteOffAmount": writeOffAmnt, "OwnershipInd":ownershipInd, "AccountStatus": acntStatus}
                            
                            if dictFlag:
                                dictFlag = False
                                crifDict.append(crDict)
                except Exception as e:
                    print("linked_accnts not found")

        except Exception as e:
            print(e)
            # if channel != 3:
            #     channel = 2
            # amberReasons.add("For CRIF: deliquencies details not found")
        
                
        if channel==1:
            notes = list(greenReasons)
        elif channel==2:
            notes = list(amberReasons)
        else:
            notes = list(redReasons)

        channels = {1:"GREEN", 2:"AMBER", 3:"RED"}
        return Response(data={"error": None, 'status': channels[channel], "totalReasons": len(notes)+len(amberReasons), 'reasons':notes,"amberReaons": amberReasons, "delinquencies":{"EXPERIAN":experianDict, "CRIF":crifDict}}, status=status.HTTP_200_OK)