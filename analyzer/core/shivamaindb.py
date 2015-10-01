#!/usr/bin/env python

from datetime import date
import time
import sys
import os

import server
import shivadbconfig
import shivanotifyerrors
import logging

import ssdeep
import MySQLdb as mdb

import urllib2
from urllib2 import HTTPError

def main():
    
    fetchfromtempdb = "SELECT `id`, `ssdeep`, `length` FROM `spam` WHERE 1"
    fetchfrommaindb = "SELECT `id`, `ssdeep`, `length` FROM `spam` WHERE 1"
    
    
    
    try:
        tempDb.execute(fetchfromtempdb)
        mainDb.execute(fetchfrommaindb)
    except mdb.Error, e:
        logging.error("[-] Error (Module shivamaindb.py) - executing fetchfromdb %s" % e)
        if notify is True:
            shivanotifyerrors.notifydeveloper("[-] Error (Module shivamaindb.py) - executing fetchfromdb %s" % e)
        
    temprecords = tempDb.fetchall()
    mainrecords = mainDb.fetchall()
    
    for t_record in temprecords:
        maxlen, minlen = int(t_record[2] * 1.10), int(t_record[2] * 0.90)
        count = 0
        
        for m_record in mainrecords:
            if m_record[2] >= minlen and m_record[2] <= maxlen:
                if t_record[0] == m_record[0]:
                    update(t_record[0], m_record[0])
                
                else:
                    ratio = ssdeep.compare(t_record[1], m_record[1])
                    # Increase the comparison ratio when length is smaller
                    if (int(t_record[2]) <= 150 and ratio >= 95) or (int(t_record[2]) > 150 and ratio >= 80):
                        update(t_record[0], m_record[0])
                    else:
                        count += 1
            else:
                count += 1
        
        if count == len(mainrecords):
            insert(t_record[0])
            
    # At last update whitelist recipients
    group_concat_max_len = "SET SESSION group_concat_max_len = 20000"
    #whitelist = "INSERT INTO `whitelist` (`id`, `recipients`) VALUES ('1', (SELECT GROUP_CONCAT(DISTINCT `to`) FROM `spam` WHERE `totalCounter` < 30)) ON DUPLICATE KEY UPDATE `recipients` = (SELECT GROUP_CONCAT(DISTINCT `to`) FROM `spam` WHERE `totalCounter` < 30)"
    
    
    whitelist = "INSERT INTO `whitelist` (`id`, `recipients`) VALUES ('1', (SELECT GROUP_CONCAT(`to`) FROM `spam` RIGHT JOIN `sdate_spam` INNER JOIN `sdate` ON (sdate.id = sdate_spam.date_id) ON (spam.id = sdate_spam.spam_id) WHERE spam.id IN (SELECT id FROM `spam` WHERE totalCounter < 100))) ON DUPLICATE KEY UPDATE `recipients` = (SELECT GROUP_CONCAT(`to`) FROM `spam` RIGHT JOIN `sdate_spam` INNER JOIN `sdate` ON (sdate.id = sdate_spam.date_id) ON (spam.id = sdate_spam.spam_id) WHERE spam.id IN (SELECT id FROM `spam` WHERE totalCounter < 100))"
  
    try:
        mainDb.execute(group_concat_max_len)
        mainDb.execute(whitelist)
    except mdb.Error, e:
        logging.error("[-] Error (Module shivamaindb.py) - executing mainDb %s" % e)
        if notify is True:
            shivanotifyerrors.notifydeveloper("[-] Error (Module shivamaindb.py) - executing mainDb %s" % e)
    
def insert(spam_id):
    
    mailFields = {'s_id':'', 'ssdeep':'', 'to':'', 'from':'', 'text':'', 'html':'', 'subject':'', 'headers':'', 'sourceIP':'', 'sensorID':'', 'firstSeen':'', 'relayCounter':'', 'relayTime':'', 'count':0, 'len':'', 'inlineFileName':[], 'inlineFilePath':[], 'inlineFileMd5':[], 'attachmentFileName':[], 'attachmentFilePath':[], 'attachmentFileMd5':[], 'links':[],  'date': '' , 'phishingHumanCheck' : '', 'shivaScore' : -1.0, 'spamassassinScore' : -1.0 }
    
    spam = "SELECT `id`, `ssdeep`, `to`, `from`, `textMessage`, `htmlMessage`, `subject`, `headers`, `sourceIP`, `sensorID`, `firstSeen`, `relayCounter`, `relayTime`, `totalCounter`, `length`, `shivaScore`, `spamassassinScore` , `phishingHumanCheck` FROM `spam` WHERE `id` = '" + str(spam_id) + "'"
    
    attachments = "SELECT `id`, `spam_id`, `file_name`, `attach_type`, `attachmentFileMd5`, `date`, `attachment_file_path` FROM `attachments` WHERE `spam_id` = '" + str(spam_id) + "'"
    
    url = "SELECT `id`, `spam_id`, `hyperlink`, `longhyperlink`, `date` FROM `links` WHERE `spam_id` = '" + str(spam_id) + "'"
    
    sensor = "SELECT `id`, `sensorID` FROM `spam` WHERE `id` = '" + str(spam_id) + "'"
    
    try:
        # Saving 'spam' table's data
        tempDb.execute(spam)
        
        spamrecord = tempDb.fetchone()
        if spamrecord:
            mailFields['s_id'], mailFields['ssdeep'], mailFields['to'], mailFields['from'], mailFields['text'], mailFields['html'], mailFields['subject'], mailFields['headers'], mailFields['sourceIP'], mailFields['sensorID'], mailFields['firstSeen'], mailFields['relayCounter'], mailFields['relayTime'], mailFields['count'], mailFields['len'], mailFields['shivaScore'], mailFields['spamassassinScore'], mailFields['phishingHumanCheck'] = spamrecord
        
            mailFields['date'] = str(mailFields['firstSeen']).split(' ')[0]
            # Saving 'attachments' table's data
            tempDb.execute(attachments)
            attachrecords = tempDb.fetchall()
            for record in attachrecords:
                
                if str(record[3]) == 'attach':  # Note: record[3] denotes 'attach_type' field in table. Could be 'attach' or 'inline'
                    mailFields['attachmentFileName'].append(record[2])
                    mailFields['attachmentFileMd5'].append(record[4])
                    mailFields['attachmentFilePath'].append(record[6])
                    
                elif str(record[3]) == 'inline':
                    mailFields['inlineFileName'].append(record[2])
                    mailFields['inlineFileMd5'].append(record[4])
                    mailFields['inlineFilePath'].append(record[6])
            
            # Saving 'links' table's data
            tempDb.execute(url)
            urlrecords = tempDb.fetchall()
            for record in urlrecords:
                mailFields['links'].append((record[2], record[3]))
            
            # Saving 'sensor' table's data
            tempDb.execute(sensor)
            sensorrecords = tempDb.fetchone()
            mailFields['sensorID'] = sensorrecords[1]
            
            
            # Inserting data in main db
            phishingHumanCheck = "'" + str(mailFields['phishingHumanCheck']) + "'" if mailFields['phishingHumanCheck'] else 'NULL'
            insert_spam = "INSERT INTO `spam`(`headers`, `to`, `from`, `subject`, `textMessage`, `htmlMessage`, `totalCounter`, `id`, `ssdeep`, `length`, `shivaScore`, `spamassassinScore`, `phishingHumanCheck`) VALUES('" + mailFields['headers'] + "', '" + mailFields['to'] + "', '" + mailFields['from'] + "', '" + mailFields['subject'] + "', '" + mailFields['text'] + "', '" + mailFields['html'] + "', '" + str(mailFields['count']) + "', '" + mailFields['s_id'] + "', '" + mailFields['ssdeep'] + "', '" + str(mailFields['len']) + "', '" + str(mailFields['shivaScore']) + "', '" + str(mailFields['spamassassinScore']) + "', " + phishingHumanCheck + ")"
            logging.debug(insert_spam)   
            try:
                mainDb.execute(insert_spam)
            except mdb.Error, e:
                logging.error("[-] Error (Module shivamaindb.py) - executing insert_spam %s" % e)
                if notify is True:
                    shivanotifyerrors.notifydeveloper("[-] Error (Module shivamaindb.py) - executing insert_spam %s" % e)
                
            insert_sdate = "INSERT INTO sdate (`date`, `firstSeen`, `lastSeen`, `todaysCounter`) VALUES('" + str(mailFields['date']) + "', '" + str(mailFields['firstSeen']) + "', '" + str(mailFields['firstSeen']) + "', '" + str(mailFields['count']) + "')"
            try:
                mainDb.execute(insert_sdate)
            except mdb.Error, e:
                logging.error("[-] Error (Module shivamaindb.py) - executing insert_sdate %s" % e)
                if notify is True:
                    shivanotifyerrors.notifydeveloper("[-] Error (Module shivamaindb.py) - executing insert_sdate %s" % e)

            insert_sdate_spam = "INSERT INTO sdate_spam (`spam_id`, `date_id`) VALUES('" + mailFields['s_id'] + "', '" + str(mainDb.lastrowid) + "')"
            
            try:
                mainDb.execute(insert_sdate_spam)
            except mdb.Error, e:
                logging.error("[-] Error (Module shivamaindb.py) - executing insert_sdate_spam %s" % e)
                if notify is True:
                    shivanotifyerrors.notifydeveloper("[-] Error (Module shivamaindb.py) - executing insert_sdate_spam %s" % e)

            ip_list = mailFields['sourceIP'].split(',')            
            for ip in ip_list:
                insert_ip = "INSERT INTO ip (`date`, `sourceIP`) VALUES('" + str(mailFields['date']) + "', '" + str(ip) + "' )"
                try:
                    mainDb.execute(insert_ip)
                except mdb.Error, e:
                    logging.error("[-] Error (Module shivamaindb.py) - executing insert_ip %s" % e)
                    if notify is True:
                        shivanotifyerrors.notifydeveloper("[-] Error (Module shivamaindb.py) - executing insert_ip %s" % e)

                insert_ip_spam = "INSERT INTO ip_spam (`spam_id`, `ip_id`) VALUES('" + str(mailFields['s_id']) + "', '" + str(mainDb.lastrowid) + "' )"
                try:
                    mainDb.execute(insert_ip_spam)
                except mdb.Error, e:
                    logging.error("[-] Error (Module shivamaindb.py) - executing insert_ip_spam %s" % e)
                    if notify is True:
                        shivanotifyerrors.notifydeveloper("[-] Error (Module shivamaindb.py) - executing insert_ip_spam %s" % e)    

            insert_sensor = "INSERT INTO sensor (`date`, `sensorID`) VALUES('" + str(mailFields['date']) + "', '" + mailFields['sensorID'] + "' )"
            try:
                mainDb.execute(insert_sensor)
            except mdb.Error, e:
                logging.error("[-] Error (Module shivamaindb.py) - executing insert_sensor %s" % e)
                if notify is True:
                    shivanotifyerrors.notifydeveloper("[-] Error (Module shivamaindb.py) - executing insert_sensor %s" % e)

            insert_sensor_spam = "INSERT INTO sensor_spam (`spam_id`, `sensor_id`) VALUES('" + str(mailFields['s_id']) + "', '" + str(mainDb.lastrowid) + "' )"
            try:
                mainDb.execute(insert_sensor_spam)
            except mdb.Error, e:
                logging.error("[-] Error (Module shivamaindb.py) - executing insert_sensor_spam %s" % e)
                if notify is True:
                    shivanotifyerrors.notifydeveloper("[-] Error (Module shivamaindb.py) - executing insert_sensor_spam %s" % e)
                
            if len(mailFields['links']) != 0:                                     # If links are present - insert into DB
                i = 0
                while i < len(mailFields['links']):
                    insert_link = "INSERT INTO links (`date`, `hyperLink`, `longHyperLink`,`spam_id` ) VALUES('" + str(mailFields['date']) + "', '" + str(mailFields['links'][i][0]) + "', " + ("NULL" if not mailFields['links'][i][1] else "'" + str(mailFields['links'][i][1]) + "'") + ", '" + str(mailFields['s_id']) + "')"
                    i += 1
                    try:
                        mainDb.execute(insert_link)
                    except mdb.Error, e:
                        logging.error("[-] Error (Module shivamaindb.py) - executing insert_link %s" % e)
                        if notify is True:
                            shivanotifyerrors.notifydeveloper("[-] Error (Module shivamaindb.py) - executing insert_link %s" % e)
            
            if int(mailFields['relayCounter']) > 0:
                insert_relay = "INSERT INTO `relay`(`date`, `firstRelayed`, `lastRelayed`, `totalRelayed`, `spam_id`, `sensorID`) VALUES ('" + str(mailFields['date']) +"', '" + str(mailFields['relayTime']) + "', '" + str(mailFields['relayTime']) + "', '" + str(mailFields['relayCounter']) + "', '" + str(mailFields['s_id']) + "', '" + str(mailFields['sensorID']) +"' )"
                
                
                try:
                    mainDb.execute(insert_relay)
                except mdb.Error, e:
                    logging.error("[-] Error (Module shivamaindb.py) - executing insert_relay %s" % e)
                    if notify is True:
                        shivanotifyerrors.notifydeveloper("[-] Error (Module shivamaindb.py) - executing insert_relay %s" % e)
                
            if len(mailFields['attachmentFileMd5']) != 0:                    # If attachment is present - insert into DB
                i = 0
                while i < len(mailFields['attachmentFileMd5']):
                    insert_attachment = "INSERT INTO `attachment`(`date`, `md5`, `attachment_file_name`, `attachment_file_path`, `attachment_file_type`, `spam_id`) VALUES('" + str(mailFields['date']) + "', '" + str(mailFields['attachmentFileMd5'][i]) + "', '" + str(mdb.escape_string(mailFields['attachmentFileName'][i].encode('utf-8'))) + "', '" + str(mdb.escape_string(mailFields['attachmentFilePath'][i].encode('utf-8'))) + "', '" + str(os.path.splitext(mdb.escape_string(mailFields['attachmentFileName'][i].encode('utf-8')))[1]) + "', '" + str(mailFields['s_id']) + "')"
                    i = i + 1
                    try:
                        mainDb.execute(insert_attachment)
                    except mdb.Error, e:
                        logging.error("[-] Error (Module shivamaindb.py) - executing insert_attachmentFileMd5 %s" % e)
                        if notify is True:
                            shivanotifyerrors.notifydeveloper("[-] Error (Module shivamaindb.py) - executing insert_attachmentFileMd5 %s" % e)

            if len(mailFields['inlineFileMd5']) != 0:                                # If inline file is present - insert into DB
                i = 0
                while i < len(mailFields['inlineFileMd5']):
                    insert_inline = "INSERT INTO `inline`(`date`, `md5`, `inline_file_name`, `inline_file_path`, `spam_id` ) VALUES('" + str(mailFields['date']) + "', '" + str(mailFields['inlineFileMd5'][i]) + "', '" + str(mdb.escape_string(mailFields['inlineFileName'][i].encode('utf-8'))) + "', '" + str(mdb.escape_string(mailFields['inlineFilePath'][i].encode('utf-8'))) + "', '" + str(mailFields['s_id']) + "')"
                    i = i + 1
                    try:
                        mainDb.execute(insert_inline)
                    except mdb.Error, e:
                        logging.error("[-] Error (Module shivamaindb.py) - executing insert_inline %s" % e)
                        if notify is True:
                            shivanotifyerrors.notifydeveloper("[-] Error (Module shivamaindb.py) - executing insert_inline %s" % e)

    except mdb.Error, e:
        logging.error("[-] Error (Module shivamaindb.py) - executing insert_spamid %s" % e)
        if notify is True:
            shivanotifyerrors.notifydeveloper("[-] Error (Module shivamaindb.py) - executing insert_spamid %s" % e)
        
    
def update(tempid, mainid):
    mailFields = {'sourceIP':'', 'sensorID':'', 'firstSeen':'', 'relayCounter':'', 'relayTime':'', 'count':0, 'inlineFileName':[], 'inlineFilePath':[], 'inlineFileMd5':[], 'attachmentFileName':[], 'attachmentFilePath':[], 'attachmentFileMd5':[], 'links':[],  'date': '', 'to': ''}
    
    tempurls = "SELECT `hyperlink`, `longhyperlink` FROM `links` WHERE `spam_id` = '" + str(tempid) + "'"
    tempattachs = "SELECT `file_name`, `attachment_file_path`, `attach_type`, `attachmentFileMd5` FROM `attachments` WHERE `spam_id` = '" + str(tempid) + "'"
    tempsensors = "SELECT `sensorID` FROM `sensors` WHERE `spam_id` = '" + str(tempid) + "'"
    tempspam = "SELECT `firstSeen`, `relayCounter`, `relayTime`, `sourceIP`, `totalCounter`, `to` FROM `spam` WHERE `id` = '" + str(tempid) + "'"
    
    try:
        tempDb.execute(tempurls)
        records = tempDb.fetchall()
        
        for record in records:
            mailFields['links'].append((record[0],record[1]))
            
            
        tempDb.execute(tempattachs)
        records = None          # To make sure that in case following query fails, we don't end up updating values from last query.
        records = tempDb.fetchall()
        
        for record in records:
            if record[2] == 'attach':           # Note: record[2] denotes 'attach_type' field in table. Could be either 'attach' or 'inline'
                mailFields['attachmentFileName'].append(record[0])
                mailFields['attachmentFileMd5'].append(record[3])
                mailFields['attachmentFilePath'].append(record[1])
                    
            elif record[2] == 'inline':
                mailFields['inlineFileName'].append(record[0])
                mailFields['inlineFileMd5'].append(record[3])
                mailFields['inlineFilePath'].append(record[1])
            
        tempDb.execute(tempsensors)   
        record = tempDb.fetchone()
        mailFields['sensorID'] = record[0]
        
        tempDb.execute(tempspam)
        record = tempDb.fetchone()
        
        mailFields['firstSeen'] = str(record[0])
        mailFields['date'] = str(record[0]).split(' ')[0]
        mailFields['relayCounter'] = record[1]
        mailFields['relayTime'] = str(record[2])
        mailFields['sourceIP'] = record[3]
        mailFields['count'] = record[4]
        mailFields['to'] = record[5]
        
        
    except mdb.Error, e:
        logging.error("[-] Error (Module shivamaindb.py) - executing temprecords %s" % e)
        if notify is True:
            shivanotifyerrors.notifydeveloper("[-] Error (Module shivamaindb.py) - executing temprecords %s" % e)
        
    # Checking for date.
    date = 0                                                                                                                   
    checkDate = "SELECT sdate.date FROM sdate JOIN sdate_spam ON (sdate.id = sdate_spam.date_id) WHERE sdate_spam.spam_id = '" + str(mainid) + "' AND sdate.date = '" + str(mailFields['date']) + "'"

    try:
        mainDb.execute(checkDate)
        if len(mainDb.fetchall()) >= 1:
            date = 1
    except mdb.Error, e:
        logging.error("[-] Error (Module shivamaindb.py) - executing checkDate %s" % e)
        if notify is True:
            shivanotifyerrors.notifydeveloper("[-] Error (Module shivamaindb.py) - executing checkDate %s" % e)   

    if date == 0:
        insert_sdate = "INSERT INTO sdate (`date`, `firstSeen`, `lastSeen`, `todaysCounter`) VALUES('" + str(mailFields['date']) + "', '" + str(mailFields['firstSeen']) + "', '" + str(mailFields['firstSeen']) + "', '" + str(mailFields['count']) + "')"
        
        try:
            mainDb.execute(insert_sdate)
        except mdb.Error, e:
            logging.error("[-] Error (Module shivamaindb.py) - insert_sdate %s" % e)
            if notify is True:
                shivanotifyerrors.notifydeveloper("[-] Error (Module shivamaindb.py) - insert_sdate %s" % e)
        
        insert_sdate_spam = "INSERT INTO sdate_spam (`spam_id`, `date_id`) VALUES('" + str(mainid) + "', '" + str(mainDb.lastrowid) + "')"
        try:
            mainDb.execute(insert_sdate_spam)
        except mdb.Error, e:
            logging.error("[-] Error (Module shivamaindb.py) - insert_sdate_spam %s" % e)
            if notify is True:
                shivanotifyerrors.notifydeveloper("[-] Error (Module shivamaindb.py) - insert_sdate_spam %s" % e)

    else:
        update_date = "UPDATE sdate JOIN sdate_spam ON (sdate.id = sdate_spam.date_id) SET sdate.lastSeen = '" + str(mailFields['firstSeen'])+"', sdate.todaysCounter = sdate.todaysCounter + '" + str(mailFields['count']) + "' WHERE sdate_spam.spam_id = '" + str(mainid) + "' AND sdate.date = '" + str(mailFields['date'])+"'"

        try:
            mainDb.execute(update_date)
        except mdb.Error, e:
            logging.error("[-] Error (Module shivamaindb.py) - update_date %s" % e)
            if notify is True:
                shivanotifyerrors.notifydeveloper("[-] Error (Module shivamaindb.py) - update_date %s" % e)
    
    
       
    # Checking for Recipients
    #recipients = str(mailFields['to']).split(", ")
    recipients = (mailFields['to'].encode('utf-8')).split(",")
    
    checkrecipientdb = "SELECT spam.to FROM spam WHERE spam.id = '" + str(mainid) + "'"
    mainDb.execute(checkrecipientdb)
    record = mainDb.fetchone()
    
    if record != None:
        recipientsdb = (record[0].encode('utf-8')).split(",")
        newrecipients = [item for item in recipients if item not in recipientsdb]
        
        if newrecipients != '':
            newrecipients = ','.join(newrecipients)
    else:
        print "no data for it in db"
        newrecipients = mailFields['to']
      
    
    # spam table - update recipients and totalCounter
    if newrecipients == '':
        update_spam = "UPDATE `spam` SET spam.totalCounter = spam.totalCounter + '" + str(mailFields['count']) + "' WHERE spam.id = '" + str(mainid) + "'"
    else:
        update_spam = "UPDATE `spam` SET spam.totalCounter = spam.totalCounter + '" + str(mailFields['count']) + "', spam.to = CONCAT(spam.to, ',', '" + str(newrecipients) + "') WHERE spam.id = '" + str(mainid) + "'"
    
    try:
        mainDb.execute(update_spam)
    except mdb.Error, e:
        logging.error("[-] Error (Module shivamaindb.py) - update_spam %s" % e)
        if notify is True:
            shivanotifyerrors.notifydeveloper("[-] Error (Module shivamaindb.py) - update_spam %s" % e)
    
    # Checking for IPs
    ip_list = str(mailFields['sourceIP']).split(", ")
    for ip in ip_list:            
        ipStatus = 1
        checkIP = "SELECT ip.sourceIP FROM ip JOIN ip_spam ON (ip.id = ip_spam.ip_id) WHERE ip_spam.spam_id = '" + str(mainid) + "' AND ip.sourceIP = '" + str(ip) + "'"

        try:
            mainDb.execute(checkIP)
            if len(mainDb.fetchall()) >= 1:
                ipStatus = 1
        except mdb.Error, e:
            logging.error("[-] Error (Module shivamaindb.py) - checkIP %s" % e)
            if notify is True:
                shivanotifyerrors.notifydeveloper("[-] Error (Module shivamaindb.py) - checkIP %s" % e)

        if ipStatus == 0:
            insert_ip = "INSERT INTO ip (`date`, `sourceIP`) VALUES('" + str(mailFields['date']) + "', '" + str(ip) + "' )"
            try:
                mainDb.execute(insert_ip)
            except mdb.Error, e:
                logging.error("[-] Error (Module shivamaindb.py) - insert_ip %s" % e)
                if notify is True:
                    shivanotifyerrors.notifydeveloper("[-] Error (Module shivamaindb.py) - insert_ip %s" % e)

            insert_ip_spam = "INSERT INTO ip_spam (`spam_id`, `ip_id`) VALUES('" + str(mainid) + "', '"+str(mainDb.lastrowid)+"')"

            try:
                mainDb.execute(insert_ip_spam)
            except mdb.Error, e:
                logging.error("[-] Error (Module shivamaindb.py) - insert_ip_spam %s" % e)
                if notify is True:
                    shivanotifyerrors.notifydeveloper("[-] Error (Module shivamaindb.py) - insert_ip_spam %s" % e)   
    
                  
            
    # Checking for Sensor ID
    sensor_list = str(mailFields['sensorID']).split(", ")
    for sensor in sensor_list:            
        sensorStatus = 1   
        checkSensorID = "SELECT sensor.sensorID FROM sensor JOIN sensor_spam ON (sensor.id = sensor_spam.sensor_id) WHERE .sensor_spam.spam_id = '" + str(mainid) + "' AND sensor.sensorID = '" + str(sensor) + "'"
        
        try:
           mainDb.execute(checkSensorID)
           if len(mainDb.fetchall()) >= 1:
                sensorStatus = 0
        except mdb.Error, e:
            logging.error("[-] Error (Module shivamaindb.py) - checkSensorID %s" % e)
            if notify is True:
                shivanotifyerrors.notifydeveloper("[-] Error (Module shivamaindb.py) - checkSensorID %s" % e)

        if sensorStatus == 1:
            insert_id = "INSERT INTO sensor (`date`, `sensorID`) VALUES('"+str(mailFields['date'])+"', '"+str(sensor)+"' )"
            try:
                mainDb.execute(insert_id)
            except mdb.Error, e:
                logging.error("[-] Error (Module shivamaindb.py) - insert_id %s" % e)
                if notify is True:
                    shivanotifyerrors.notifydeveloper("[-] Error (Module shivamaindb.py) - insert_id %s" % e)

            insert_id_spam = "INSERT INTO sensor_spam (`spam_id`, `sensor_id`) VALUES('" + str(mainid) + "', '" + str(mainDb.lastrowid)+"')"

            try:
                mainDb.execute(insert_id_spam)
            except mdb.Error, e:
                logging.error("[-] Error (Module shivamaindb.py) - insert_id_spam %s" % e)
                if notify is True:
                    shivanotifyerrors.notifydeveloper("[-] Error (Module shivamaindb.py) - insert_id_spam %s" % e)

  
    # Checking for URLs
    for url in mailFields['links']:
        urlstatus = 1
        checkURL = "SELECT `hyperLink` FROM `links` WHERE `spam_id` = '" + str(mainid) + "' AND `hyperLink` = '" + str(url[0]) + "'"
        try:
            mainDb.execute(checkURL)
            records = mainDb.fetchall()
        except mdb.Error, e:
            logging.error("[-] Error (Module shivamaindb.py) - checkURL %s" % e)
            if notify is True:
                shivanotifyerrors.notifydeveloper("[-] Error (Module shivamaindb.py) - checkURL %s" % e)
            
        if len(records) >= 1:
            urlstatus = 0
        
        if urlstatus == 1:
            insert_url = "INSERT INTO `links`(`date`, `hyperLink`, `longHyperLink`, `spam_id`) VALUES ('" + str(mailFields['date']) + "', '" + str(url[0]) + "', " + ("NULL" if not url[1] else "'" + str(url[1]) + "'") + ", '" + str(mainid) + "')"
            try:
                mainDb.execute(insert_url)
            except mdb.Error, e:
                logging.error("[-] Error (Module shivamaindb.py) - insert_url %s" % e)
                if notify is True:
                    shivanotifyerrors.notifydeveloper("[-] Error (Module shivamaindb.py) - insert_url %s" % e)

    # Checking fo attachments
    if len(mailFields['attachmentFileMd5']) != 0:
        i = 0
        while i < len(mailFields['attachmentFileMd5']):
            md5Status = 1
            checkMd5 = "SELECT `md5` FROM `attachment` WHERE `spam_id` = '" + str(mainid) + "' AND `md5` = '" + str(mailFields['attachmentFileMd5'][i]) + "'"
            try:
                mainDb.execute(checkMd5)
                records = mainDb.fetchall()
            except mdb.Error, e:
                logging.error("[-] Error (Module shivamaindb.py) - checkMd5 %s" % e)
                if notify is True:
                    shivanotifyerrors.notifydeveloper("[-] Error (Module shivamaindb.py) - checkMd5 %s" % e)
            
            if len(records) >= 1:
                md5Status = 0
                
            if md5Status == 1:
                insert_attachment = "INSERT INTO `attachment`(`date`, `md5`, `attachment_file_name`, `attachment_file_path`, `attachment_file_type`, `spam_id`) VALUES('" + str(mailFields['date']) + "', '" + str(mailFields['attachmentFileMd5'][i]) + "', '" + str(mdb.escape_string(mailFields['attachmentFileName'][i].encode('utf-8'))) + "', '" + str(mdb.escape_string(mailFields['attachmentFilePath'][i].encode('utf-8'))) + "', '" + str(os.path.splitext(mailFields['attachmentFileName'][i])[1].encode('utf-8')) + "', '" + str(mainid) + "')"
                
                try:
                    mainDb.execute(insert_attachment)
                except mdb.Error, e:
                    logging.error("[-] Error (Module shivamaindb.py) - insert_attachment %s" % e)
                    if notify is True:
                        shivanotifyerrors.notifydeveloper("[-] Error (Module shivamaindb.py) - insert_attachment %s" % e)
            i = i + 1
    
    # Checking fo inline attachments
    if len(mailFields['inlineFileMd5']) >= 1:
        i = 0
        while i < len(mailFields['inlineFileMd5']):
            md5Status = 1
            checkMd5 = "SELECT `md5` FROM `inline` WHERE `spam_id` = '" + str(mainid) + "' AND `md5` = '" + str(mailFields['inlineFileMd5'][i]) + "'"
            try:
                mainDb.execute(checkMd5)
                records = mainDb.fetchall()
            except mdb.Error, e:
                logging.error("[-] Error (Module shivamaindb.py) - checkMd5 %s" % e)
                if notify is True:
                    shivanotifyerrors.notifydeveloper("[-] Error (Module shivamaindb.py) - checkMd5 %s" % e)
            
            if len(records) >= 1:
                md5Status = 0
                
            if md5Status == 1:
                insert_inline = "INSERT INTO `inline`(`date`, `md5`, `inline_file_name`, `inline_file_path`, `spam_id` ) VALUES('" + str(mailFields['date']) + "', '" + str(mailFields['inlineFileMd5'][i]) + "', '" + str(mdb.escape_string(mailFields['inlineFileName'][i])) + "', '" + str(mdb.escape_string(mailFields['inlineFilePath'][i])) + "', '" + str(mainid) + "')"
                try:
                    mainDb.execute(insert_inline)
                except mdb.Error, e:
                    logging.error("[-] Error (Module shivamaindb.py) - insert_inline %s" % e)
                    if notify is True:
                        shivanotifyerrors.notifydeveloper("[-] Error (Module shivamaindb.py) - insert_inline %s" % e)
            i = i + 1
            
    # Last but not the least, updating relay table.
    if int(mailFields['relayCounter']) > 0:
        relayDate = str(mailFields['relayTime']).split(' ')[0]
        checkRelayDate = "SELECT `id` FROM `relay` WHERE `spam_id` = '" + str(mainid) + "' AND `date` = '" + str(relayDate) + "'"
        try:
            mainDb.execute(checkRelayDate)
        except mdb.Error, e:
            logging.error("[-] Error (Module shivamaindb.py) - checkRelayDate %s" % e)
            if notify is True:
                shivanotifyerrors.notifydeveloper("[-] Error (Module shivamaindb.py) - checkRelayDate %s" % e)
            
        if len(mainDb.fetchall()) >= 1:
            update_relay = "UPDATE `relay` SET `lastRelayed` = '" + str(mailFields['relayTime']) + "', totalRelayed = totalRelayed + '" + str(mailFields['relayCounter']) + "' WHERE `spam_id` = '" + str(mainid) + "' AND `date` = '" + str(relayDate) + "'"
            try:
                mainDb.execute(update_relay)
            except mdb.Error, e:
                logging.error("[-] Error (Module shivamaindb.py) - update_relay %s" % e)
                if notify is True:
                    shivanotifyerrors.notifydeveloper("[-] Error (Module shivamaindb.py) - update_relay %s" % e)
            
        else:
            insert_relay = "INSERT INTO `relay`(`date`, `firstRelayed`, `lastRelayed`, `totalRelayed`, `spam_id`, `sensorID`) VALUES ('" + str(relayDate) + "', '" + str(mailFields['relayTime']) + "', '" + str(mailFields['relayTime']) + "', '" + str(mailFields['relayCounter']) + "', '" + str(mainid) + "', '" + str(mailFields['sensorID']) + "')"
            try:
                mainDb.execute(insert_relay)
            except mdb.Error, e:
                logging.error("[-] Error (Module shivamaindb.py) - insert_relay %s" % e)
                if notify is True:
                    shivanotifyerrors.notifydeveloper("[-] Error (Module shivamaindb.py) - insert_relay %s" % e)
             

"""
retrieve spam from database
limit - integer, how many records should be retrieved
offset - integer, offset to start from
filter = ('none','phish','spam')
"""
def retrieve(limit, offset, filterType="none"):
    """retrieve list e-mails stored in database

    Keyword arguments:
    limit -- integer
    offset -- integer
    """ 
    whereclause = '1'   
    if filterType == 'phish':
        whereclause = 'phishingHumanCheck is true'
    
    if filterType == 'spam':
        whereclause = 'phishingHumanCheck is not true'

    fetchidsquery = "SELECT `id` FROM `spam` WHERE " + whereclause + " ORDER BY `id` LIMIT " + str(limit) + " OFFSET " + str(offset)
    
    try:
        mainDb = shivadbconfig.dbconnectmain()
        mainDb.execute(fetchidsquery)
        
        ids = mainDb.fetchall()
        return retrieve_by_ids(map(lambda a: a[0], ids if ids else []))
    
    except mdb.Error, e:
        logging.error(e)
        
    return []

def retrieve_by_ids(email_ids = []):
    resultlist = []
    try:
        for current_id in email_ids:
            mailFields = {'s_id':'', 'ssdeep':'', 'to':'', 'from':'', 'text':'', 'html':'', 'subject':'', 'headers':'', 'sourceIP':'', 'sensorID':'', 'firstSeen':'', 'relayCounter':'', 'relayTime':'', 'count':0, 'len':'', 'inlineFileName':[], 'inlineFilePath':[], 'inlineFileMd5':[], 'attachmentFileName':[], 'attachmentFilePath':[], 'attachmentFileMd5':[], 'attachmentFileType':[], 'links':[],  'date': '' }
            
            """fetch basic spam information from database"""
            spamquery = "SELECT `from`,`subject`,`to`,`textMessage`,`htmlMessage`,`totalCounter`,`ssdeep`,`headers`,`length`,`phishingHumanCheck`,`shivaScore`,`spamassassinScore` FROM `spam` WHERE `id` = '" + current_id + "'"
            mailFields['s_id'] = current_id
            
            mainDb = shivadbconfig.dbconnectmain()
            mainDb.execute(spamquery)

            current_record = mainDb.fetchone()
            if not current_record: 
                continue
            
            mailFields['from'] = current_record[0] 
            mailFields['subject'] = current_record[1]
            mailFields['to'] = current_record[2]
            mailFields['text'] = current_record[3]
            mailFields['html'] = current_record[4]
            mailFields['totalCounter'] = current_record[5]
            mailFields['ssdeep'] = current_record[6]
            mailFields['headers'] = current_record[7]
            mailFields['len'] = current_record[8]
            mailFields['phishingHumanCheck'] = current_record[9]
            mailFields['shivaScore'] = current_record[10]
            mailFields['spamassassinScore'] = current_record[11]
            
            """fetch links for current spam"""
            linksquery = "SELECT `hyperLink`, `longHyperLink`  FROM `links` WHERE `spam_id` = '" + current_id + "'"
            mainDb.execute(linksquery);
            links = mainDb.fetchall()
            linkList = []
            """check for possible url shortening"""
            for link in links:
                linkList.append((link[0],link[1]))
            mailFields['links'] = linkList
            
            """fetch attachments for current spam"""
            attachmentsquery = "SELECT `attachment_file_name`,`attachment_file_path`,`attachment_file_type` FROM `attachment` WHERE `spam_id` = '" + current_id + "'"
            mainDb.execute(attachmentsquery);
            attachments = mainDb.fetchall()
            for row in attachments:
                mailFields['attachmentFileName'].append(row[0]) 
                mailFields['attachmentFilePath'].append(row[1])
                mailFields['attachmentFileType'].append(row[2])
            
            
            resultlist.append(mailFields)
        return resultlist
    except mdb.Error, e:
        logging.error(e)
    
    return resultlist
    
    
def get_overview(start=0,limit=10):
    overview_list = []
    try:
        overview_query = "SELECT `id`,`firstSeen`,`lastSeen`,`subject`,`shivaScore`,`spamassassinScore`,`sensorID`,`derivedPhishingStatus` from `spam_overview_view` LIMIT {0} OFFSET {1}".format(str(limit),str(start))
        
        mainDb = shivadbconfig.dbconnectmain()
        mainDb.execute(overview_query)
        result = mainDb.fetchall()
        
        overview_list = []
        for record in result:
            overview_list.append({'id':record[0], 'firstSeen':record[1], 'lastSeen':record[2], 'subject':record[3], 'shivaScore':record[4], 'spamassassinScore':record[5], 'sensorID':record[6], 'derivedPhishingStatus':record[7]})
        
        
    except mdb.Error, e:
        logging.error(e)
        
    return overview_list
    
def get_mail_count():
    query = "SELECT COUNT(*) FROM spam"
    
    result = 0
    try:
        mainDb = shivadbconfig.dbconnectmain()
        mainDb.execute(query)
        result = mainDb.fetchone()[0]
    except mdb.Error, e:
        logging.error(e)
        
    return result

def delete_spam(email_id=''):
    """delete email from database and remove all related files"""
    if not email_id:
        return
    
    delete_queries = []
    
    check_query = "SELECT * FROM `spam` WHERE email_id =  '{}'".format(email_id);
    mainDb = shivadbconfig.dbconnectmain()
    
    mainDb.execute(check_query)
    if not mainDb.fetchone():
        return
    
    delete_queries.append("DELETE FROM attachment WHERE spam_id = '{}'".format(email_id))
    atachments_query = "SELECT date_id FROM sdate_spam WHERE spam_id = '{}'".format(email_id)
    mainDb.execute(atachments_query)
    records = mainDb.fetchall()
    if records:
        for record in records:
            __silent_remove_file(str(record[0]))
            
    rawspampath = server.shivaconf.get('analyzer', 'rawspampath')
    for subdir in ('phishing/', 'spam/'):
        from os import listdir
        from os.path import isfile, join
        path = rawspampath + subdir
        files = [ f for f in listdir(path) if isfile(join(path,f)) and f.startswith(email_id) ]
        for file_to_delete in files:
            __silent_remove_file(path + file_to_delete)
            
    delete_queries.append("DELETE FROM inline WHERE spam_id = '{}'".format(email_id))
    delete_queries.append("DELETE FROM links WHERE spam_id = '{}'".format(email_id))
    delete_queries.append("DELETE FROM relay WHERE spam_id = '{}'".format(email_id))
    
    ips_query = "SELECT ip_id FROM ip_spam WHERE spam_id = '{}'".format(email_id)
    delete_queries.append("DELETE FROM ip_spam WHERE spam_id = '{}'".format(email_id))
    mainDb.execute(ips_query)
    records = mainDb.fetchall()
    if records:
        for record in records:
            delete_queries.append("DELETE FROM ip WHERE email_id = '{}'".format(str(record[0])))
    

    dates_query = "SELECT date_id FROM sdate_spam WHERE spam_id = '{}'".format(email_id)
    delete_queries.append("DELETE FROM sdate_spam WHERE spam_id = '{}'".format(email_id))
    mainDb.execute(dates_query)
    records = mainDb.fetchall()
    if records:
        for record in records:
            delete_queries.append("DELETE FROM sdate WHERE email_id = '{}'".format(str(record[0])))
    
    
    sensors_query = "SELECT sensor_id FROM sensor_spam WHERE spam_id = '{}'".format(email_id)
    delete_queries.append("DELETE FROM sensor_spam WHERE spam_id = '{}'".format(email_id))
    mainDb.execute(sensors_query)
    records = mainDb.fetchall()
    if records:
        for record in records:
            delete_queries.append("DELETE FROM sensor WHERE email_id = '{}'".format(str(record[0])))
    

    delete_queries.append("DELETE FROM spam WHERE email_id = '{}'".format(email_id))
    for query in delete_queries:
        try:
            mainDb.execute(query)
        except mdb.Error, e:
            logging.error(e)
            return
        
    logging.info("Email with email_id '{}' was successfully deleted from honeypot".format(email_id))
           

def mark_as_phishing(email_id=''):
    """mark email with given id as phishing"""
    
    logging.info(get_derived_phishing_status(email_id))
    if get_derived_phishing_status(email_id):
        logging.info("Atempnt to re-mark email with id '{}' as phishing, nothing to do".format(email_id))
        return
    
    logging.info("Manually marking email with id '{}' as phishing.".format(email_id))
    
    update_query = "update spam set derivedPhishingStatus = true where id = '{}'".format(email_id)
    try:
        mainDb = shivadbconfig.dbconnectmain()
        mainDb.execute(update_query)
    except mdb.Error, e:
        logging.error(e)
        return
    
    __move_mail_by_id(email_id, False)
    
    
    
    
def mark_as_spam(email_id=''):
    """mark email with given id as spam"""
    
    if get_derived_phishing_status(email_id) == False:
        logging.info("Atempnt to re-mark email with id '{}' as spam, nothing to do".format(email_id))
        return
    
    logging.info("Manually marking email with id '{}' as spam.".format(email_id))
    
    update_query = "update spam set derivedPhishingStatus = False where id = '{}'".format(email_id)
    try:
        mainDb = shivadbconfig.dbconnectmain()
        mainDb.execute(update_query)
    except mdb.Error, e:
        logging.error(e)
        return
    
    __move_mail_by_id(email_id, True)
    
def __move_mail_by_id(email_id='',spam_to_pshishing=True):
    rawspampath = server.shivaconf.get('analyzer', 'rawspampath')
    phish_path = rawspampath + 'phishing/'
    spam_path = rawspampath + 'spam/'
    
    to_path = spam_path if spam_to_pshishing else phish_path
    from_path = phish_path if spam_to_pshishing else spam_path
    

    files_to_move = list()
    from os import walk,rename
    for dirpath, dirnames, filenames in walk(from_path):
        for filename in filenames:
            if filename.startswith(email_id):
                files_to_move.append(filename)
    
             
    for filename in files_to_move:
        logging.info(from_path + filename)
        rename(from_path + filename, to_path + filename)
    
    
def get_derived_phishing_status(email_id=''):
    """ return True if email with given id was classified as phishing,
        False if it was classified as spam
        None if if information isn't available (imported emails).
    """
    
    if not email_id:
        return None
    
    query = 'SELECT derivedPhishingStatus FROM spam WHERE id = \'{}\''.format(email_id)
    try:
        mainDb = shivadbconfig.dbconnectmain()
        mainDb.execute(query)
    except mdb.Error, e:
        logging.error(e)
        return None
    
    result = mainDb.fetchone()[0]
    if result == True:
        return True
    if result == False:
        return False
    return None
    

def __silent_remove_file(filename):
    try:
        os.remove(filename)
    except OSError:
        pass  


if __name__ == '__main__':
    tempDb = shivadbconfig.dbconnect()
    mainDb = shivadbconfig.dbconnectmain()
    notify = server.shivaconf.getboolean('notification', 'enabled')
#     time.sleep(200) # Giving time to hpfeeds module to complete the task.
    logging.basicConfig(filename='logs/maindb.log',level=logging.DEBUG,format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    main()
