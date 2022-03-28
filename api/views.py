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
        redReasons = [] #stores all rejection reasons
        greenReasons = [] #stores all acceptance reasons
        amberReasons = [] #stores all amber case reasons
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
            return Response(data={"error": "Experian file not found or not in proper format", 'status': "", 'reasons': "", "delinquencies":{"EXPERIAN":{}, "CRIF":{}}}, status = status.HTTP_406_NOT_ACCEPTABLE) 
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
            return Response(data={"error": "CRIF file not found or not in proper format", 'status': "", 'reasons': "", "delinquencies":{"EXPERIAN":{}, "CRIF":{}}}, status = status.HTTP_406_NOT_ACCEPTABLE) 
        #END


        if (not crifData) and (not experianData):
            return Response(data={"error": "CRIF and Experian file not found or not in proper format", 'status': "", 'reasons': "", "delinquencies":{"EXPERIAN":{}, "CRIF":{}}}, status = status.HTTP_406_NOT_ACCEPTABLE) 

        experianHTML = ''
        if(experianData):
            try:
                experianHTML = experianData["experianProviderResponse"]["showHtmlReportForCreditReport"]
                experianHTML = html.unescape(experianHTML)
                # print(experianHTML)
            except Exception as e:
                print(e)
                return Response(data={"error": "Experian file not found or not in proper format", 'status': "", 'reasons': "", "delinquencies":{"EXPERIAN":{}, "CRIF":{}}}, status = status.HTTP_406_NOT_ACCEPTABLE) 

        else:
            pass
        
         #Experian processing
        try:
            experianSoup = BeautifulSoup(experianHTML, 'xml')
            experianSoup = experianSoup.find('INProfileResponse')
        except Exception as e:
            print(e)
            return Response(data={"error": "Experian file not found or not in proper format", 'status': "", 'reasons': "", "delinquencies":{"EXPERIAN":{}, "CRIF":{}}}, status = status.HTTP_406_NOT_ACCEPTABLE) 
        
        experianScore = self.getExperianScore(experianSoup)
        # print(experianScore)
        if(experianScore):
            # print(experianScore)
            experianScore = float(experianScore)
            if experianScore < 600:
                channel = 3
                redReasons.append("Experian score below 600")
            elif experianScore >=600 and experianScore <=700:
                channel = 2
                amberReasons.append("Experian score is in 600 to 700 range")
            elif experianScore > 700:
                channel = 1
                greenReasons.append("Experian score is more than 700")
        else:
            amberReasons.append("Experian Score not available")
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
                return Response(data={"error": "CRIF file not found or not in proper format", 'status': "", 'reasons': "", "delinquencies":{"EXPERIAN":{}, "CRIF":{}}}, status = status.HTTP_406_NOT_ACCEPTABLE) 

        else:
            pass
        

        #CRIF processing
        try:
            crifSoup = BeautifulSoup(crifHTML, 'xml')
            crifSoup = crifSoup.find('B2C-REPORT')
        except Exception as e:
            print(e)
            return Response(data={"error": "CRIF file not found or not in proper format", 'status': "", 'reasons': "", "delinquencies":{"EXPERIAN":{}, "CRIF":{}}}, status = status.HTTP_406_NOT_ACCEPTABLE) 

        crifScore = self.getCrifScore(crifSoup)
        # print(crifScore)
        if(crifScore):
            # print(crifScore)
            crifScore = float(crifScore)
            if crifScore < 600:
                channel = 3
                redReasons.append("CRIF score below 600")
            elif crifScore >= 600 and crifScore < 650:
                if channel != 3:
                    channel = 2
                amberReasons.append("CRIF score in between 600 to 650")
            elif crifScore >= 650:
                if(channel <=1):
                    channel = 1
                    greenReasons.append("CRIF score is more than 650")
        else:
            amberReasons.append("CRIF Score not available")
            channel = 2
        
        #checking delinquency
        experianDict = {}
        experianGreenFlag = True
        experianGreenFlagB = True #used to remove duplicacy of green channel reasons
        exAmberFlag = True #used to remove duplicacy of amber channel reasons
        try:
            cias_accounts = experianSoup.find('CAIS_Account').findAll('CAIS_Account_DETAILS')
            # print(cias_accounts)
            for accnt in cias_accounts:
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
                        amntFinanced = experianSoup.find('Current_Application').find('Current_Application_Details').find('Amount_Financed').get_text().strip()
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
                        experianGreenFlag = False
                        if accntType != '10':
                            redReasons.append("For Experian: Account type is not credit card and amount past due is greater than 1000")
                        else:
                            redReasons.append("For Experian: Account type is credit card and amount past due is greater than 10000")
                        
                        experianDict = {"AmountPastDue": amount_past_due, "SubscriberName":subName, "AmountFinanced":amntFinanced, "AccountType":accntType, "SuitFiledWillfulDefaultWrittenOffStatus":sfwf, "AccountHolderType":acntHolderType, "AccountStatus":acntStatus}
                        break
                                        
                    elif ((accntType == '10' and amount_past_due<=10000) or (accntType != '10' and amount_past_due==0)) and experianGreenFlagB:
                        experianGreenFlag = False
                        experianGreenFlagB = False
                        if channel <=1:
                            channel = 1
                            if accntType == '10':
                                greenReasons.append("For Experian: Account type is 10 and amount past due is less than equal to 10000")
                            else:
                                greenReasons.append("For Experian: Account type is not equal to 10 and amount past due is 0 or not found")
                    # else:
                    #     if channel != 3 and exAmberFlag:
                    #         channel = 2
                    #         exAmberFlag = False
                    #         experianDict = {"AmountPastDue": amount_past_due, "SubscriberName":subName, "AmountFinanced":amntFinanced, "AccountType":accntType, "SuitFiledWillfulDefaultWrittenOffStatus":sfwf, "AccountHolderType":acntHolderType, "AccountStatus":acntStatus}
                    #         notes.append("Amount past due or account type is not found")
                    #         break
                except Exception as e:
                    print("Amount past due amount not found")
                    if channel != 3 and exAmberFlag:
                        channel = 2
                        exAmberFlag = False
                        amberReasons.append("For Experian: overdue amount not available")
        except Exception as e:
            print(e)
            if channel <=1:
                channel = 1
                greenReasons.append("For Experian: deliquencies details not found")
        
        if(experianGreenFlag):
            if channel != 3:
                channel = 2
                amberReasons.append("For Experian: deliquencies are not in given constraints")

        
        crifDict = {}
        crifGreenFlag = True
        crifGreenFlagB = True #used to remove duplicacy of green channel reasons 
        crifGreenFlagC = True #used to remove duplicacy of green channel reasons 
        crifAmberFlag = True #used to remove duplicacy of amber channel reasons
        redFlagB = True #used to remove duplicacy of red channel reasons
        try:
            crifResponses = crifSoup.find('RESPONSES').findAll('RESPONSE')
            # print(crifResponses)

            for loans in crifResponses:
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
                    if (acntStatus == "substandard" or acntStatus == "doubtful" or acntStatus == "special mention account" or acntStatus == "loss" or acntStatus == "active") and redFlagB:
                        channel = 3
                        redFlagB = False
                        redReasons.append("For CRIF: Loan status is Substandard, Doubtful, Special mention account, loss, Active")
                        crifDict = {"OverdueAmount": overdueAmount, "AccountType": accntType, "CreditGuarantor": creditGrntr, "DisbursedAmount": disbursedAmnt, "WriteOffAmount": writeOffAmnt, "OwnershipInd":ownershipInd, "AccountStatus": acntStatus}
                    else:
                        if channel <= 1 and crifGreenFlagC:
                            channel = 1
                            crifGreenFlagC = False
                            greenReasons.append("In CRIF: No Substandard, Doubtful, Special mention account and loss, Written-off,willful default and settled")


                    if (overdueAmount > 1000 and accntType != "credit card") or (accntType == 'credit card' and overdueAmount>10000):
                        channel = 3
                        crifGreenFlag = False
                        if(accntType != "credit card"):
                            redReasons.append("For CRIF: Account Type is not creadit card and overdue amount is above 1000")
                        else:
                            redReasons.append("For CRIF: Account Type is creadit card and overdue amount is above 10000")
                        
                        crifDict = {"OverdueAmount": overdueAmount, "AccountType": accntType, "CreditGuarantor": creditGrntr, "DisbursedAmount": disbursedAmnt, "WriteOffAmount": writeOffAmnt, "OwnershipInd":ownershipInd, "AccountStatus": acntStatus}
                        break
                    elif (accntType == "credit card" and overdueAmount <= 10000) or (accntType != 'credit card' and overdueAmount == 0) and crifGreenFlagB:
                        # print("green")
                        crifGreenFlag = False
                        crifGreenFlagB = False
                        if channel <=1:
                            channel = 1
                            if accntType == "credit card":
                                greenReasons.append("For CRIF: Account type is credit card and overdueAmount less than equal to 10000")
                            else:
                                greenReasons.append("For CRIF: Account type is not credit card and overdueAmount is 0 or not found")

                except Exception as e:
                    print("overdue amount not found")
                    if channel != 3 and crifAmberFlag:
                        channel = 2
                        crifAmberFlag = False
                        amberReasons.append("For CRIF: overdue amount not available")
                try:
                    linked_accnts = loans.find('LOAN-DETAILS').find("LINKED-ACCOUNTS").findAll("ACCOUNT-DETAILS")
                    for accnts in linked_accnts:
                        try:
                            overdueAmount = accnts.find('OVERDUE-AMT').get_text().strip()
                            if(overdueAmount):
                                overdueAmount = float(overdueAmount)
                            else:
                                overdueAmount = 0
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

                            acntStatus = acntStatus.lower()
                            if acntStatus == "substandard" or acntStatus == "doubtful" or acntStatus == "special mention account" or acntStatus == "loss" or acntStatus == "active" and redFlagB:
                                channel = 3
                                redFlagB = True
                                redReasons.append("For CRIF: Loan status is Substandard, Doubtful, Special mention account, loss, Active")
                                crifDict = {"OverdueAmount": overdueAmount, "AccountType": accntType, "CreditGuarantor": creditGrntr, "DisbursedAmount": disbursedAmnt, "WriteOffAmount": writeOffAmnt, "OwnershipInd":ownershipInd, "AccountStatus": acntStatus}
                            else:
                                if channel <= 1 and crifGreenFlagC:
                                    channel = 1
                                    crifGreenFlagC = True
                                    greenReasons.append("In CRIF: No Substandard, Doubtful, Special mention account and loss, Written-off,willful default and settled")


                            if (overdueAmount > 1000 and accntType != "credit card") or (accntType == 'credit card' and overdueAmount>10000):
                                channel = 3
                                crifGreenFlag = False
                                if(accntType != "credit card"):
                                    redReasons.append("For CRIF: Account Type is not creadit card and overdue amount is above 1000")
                                else:
                                    redReasons.append("For CRIF: Account Type is creadit card and overdue amount is above 10000")
                                
                                crifDict = {"OverdueAmount": overdueAmount, "AccountType": accntType, "CreditGuarantor": creditGrntr, "DisbursedAmount": disbursedAmnt, "WriteOffAmount": writeOffAmnt, "OwnershipInd":ownershipInd, "AccountStatus": acntStatus}
                                break
                            elif (accntType == "credit card" and overdueAmount <= 10000) or (accntType != 'credit card' and overdueAmount == 0) and crifGreenFlagB:
                                # print("green")
                                crifGreenFlag = False
                                crifGreenFlagB = False
                                if channel <=1:
                                    channel = 1
                                    if accntType == "credit card":
                                        greenReasons.append("For CRIF: Account type is credit card and overdueAmount less than equal to 10000")
                                    else:
                                        greenReasons.append("For CRIF: Account type is not credit card and overdueAmount is 0 or not found")

                        except Exception as e:
                            print("overdue amount not found")
                            if channel != 3 and crifAmberFlag:
                                channel = 2
                                crifAmberFlag = False
                                amberReasons.append("For CRIF: overdue amount not available")

                except Exception as e:
                    print("linked_accnts not found")

        except Exception as e:
            print(e)
            if channel != 3:
                channel = 2
                amberReasons.append("For CRIF: deliquencies details not found")
        
        if(crifGreenFlag):
            if channel != 3:
                channel = 2
                amberReasons.append("For CRIF: deliquencies are not in given constraints")
        
        #assests classification
        amberFlagA = True #used to remove duplicacy of amber channel reasons
        amberFlagB = True #used to remove duplicacy of amber channel reasons
        amberFlagC = True #used to remove duplicacy of amber channel reasons
        redFlag = True #used to remove duplicacy of red channel reasons
        greenFlag = True #used to remove duplicacy of green channel reasons
        try:
            cias_accounts = experianSoup.find('CAIS_Account').findAll('CAIS_Account_DETAILS')
            for accnt in cias_accounts:
                amount_past_due = 0
                try:
                    amount_past_due = accnt.find('Amount_Past_Due').get_text().strip()
                    if(amount_past_due):
                        amount_past_due = float(amount_past_due)
                except Exception as e:
                    print(e)
                   
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
                    amntFinanced = experianSoup.find('Current_Application').find('Current_Application_Details').find('Amount_Financed').get_text().strip()
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
                                amberFlagA = False
                                amberReasons.append("For Experian: asset_classification not available")

                        dpd = None
                        try:
                            dpd = history.find("Days_Past_Due").get_text().strip()
                        except Exception as e:
                            print("days past due not found")
                            if channel != 3 and amberFlagB:
                                channel = 2 
                                amberFlagB = False
                        
                        if dpd != None and int(dpd) >= 90 and redFlag:
                            channel = 3
                            redFlag = False
                            redReasons.append("For Experian: DPD more than 90 days")
                            experianDict = {"AmountPastDue": amount_past_due, "SubscriberName":subName, "AmountFinanced":amntFinanced, "AccountType":accntType, "SuitFiledWillfulDefaultWrittenOffStatus":sfwf, "AccountHolderType":acntHolderType, "AccountStatus": acntStatus}
                        
                        if asset_classification == "B" or asset_classification == "D" or asset_classification == "M" or asset_classification == "L" :
                            channel = 3
                            redReasons.append("For Experian: Case of wilful default, written off, suit filed  in any of the loans")
                            experianDict = {"AmountPastDue": amount_past_due, "SubscriberName":subName, "AmountFinanced":amntFinanced, "AccountType":accntType, "SuitFiledWillfulDefaultWrittenOffStatus":sfwf, "AccountHolderType":acntHolderType, "AccountStatus":acntStatus}
                            break
                        elif asset_classification != None:
                            if channel <=1 and greenFlag:
                                channel = 1
                                greenFlag = False
                                greenReasons.append("For Experian: No written-off, willful default, Substandard, Doubtful, Special mention account and loss and settled status of loan")
                except Exception as e:
                    print("Account history not found")
                    if channel != 3 and amberFlagC:
                        channel = 2
                        amberFlagC = False
                        amberReasons.append("For Experian: Account history not available")
        except Exception as e:
            print(e)
            if channel != 3:
                channel = 2
                amberReasons.append("For Experian: Account history not available")
        
        try:
            pass
        except Exception as e:
            print(e)
        
        try:
            crifResponses = crifSoup.find('RESPONSES').findAll('RESPONSE')
        except Exception as e:
            print(e)        

        if channel==1:
            notes = greenReasons
        elif channel==2:
            notes = amberReasons
        else:
            notes = redReasons

        channels = {1:"GREEN", 2:"AMBER", 3:"RED"}
        return Response(data={"error": None, 'status': channels[channel], 'reasons':notes, "delinquencies":{"EXPERIAN":experianDict, "CRIF":crifDict}}, status=status.HTTP_200_OK)