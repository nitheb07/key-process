"""
decipher .ekb file
 and save files in folder

"""

import datetime
import os.path
import urllib
import uuid
import time
import zipfile
import boto3

s3_client = boto3.resource('s3')
bucket = s3_client.Bucket('keyprocess-processed')


def rot48x(instr):
    nstr = ''
    for c in instr:
        cv = ord(c)
        if cv >= 32 and cv < 128:
            cv = (cv - 32 + 48) % 96 + 32
        nstr = nstr + chr(cv)
    return nstr


"""
LICENSEE=HPLself
BUILD=20100110
EXPIRATION=20101231
EXTDATE=20391231
KIND=CLINIC
DONGLE=50024
DONGLE=50026
DONGLE=51695
"""


def _licefile(lns):
    bdate = None
    expdate = None
    extdate = None
    kind = None
    licto = None
    donglist = []
    for lv in lns:
        line = lv.strip()
        if line[:6] == 'BUILD=':
            bdate = int(line[6:])
        elif line[:8] == 'EXTDATE=':
            extdate = line[8:]
        elif line[:11] == 'EXPIRATION=':
            expdate = int(line[11:])
        elif line[:11] == 'LICENSEDTO=':
            licto = line[11:]
        elif line[:5] == 'KIND=':
            kind = line[5:]
        elif line[:7] == 'DONGLE=':
            donglist.append(int(line[7:]))
    if extdate:
        expdate = extdate

    return bdate, expdate, kind, licto, donglist

"""
FEATURES
LICENSEE=HPLself
BUILD=20100110
EXPIRATION=20101231
DONGLE=50024
DONGLE=50026
DONGLE=51695
SYNCHRONY=YES
ALPHATHETA=YES
BETASMR=YES
TACTILE=YES
PERIPHDISPLAY=YES
*****EXPORT=YES
*****MULTIDISPLAY=YES
*****EGSBYPASSYES
*****EGSBYPASS=YES
*****FEATURE1=YES
ZSCORE=YES
FEATURE3=YES
FEATURE4=YES
FEATURE5=YES
FEATURE6=YES
FEATURE6PWD=8424229CCB0A37D6C9D64D11A0263146
EXPORTALL
AMPENABLES
4-CHANNEL
SUB_HZ
REVIEWALL
SUPERV_R
FULLRECORD
ADVMODES
STUDY_EN
VERSION43
VERSION44
"""
features = ['SYNCHRONY=', 'ALPHATHETA=', 'BETASMR=', 'TACTILE=', 'PERIPHDISPLAY=',
            'ZSCORE=', 'FEATURE3=', 'FEATURE4=', 'FEATURE5=', 'FEATURE6=', 'AMPENABLES=', 'VERSION43=',
            'VERSION44=', 'STUDY_EN', 'ADVMODES', 'FULLRECORD', 'SUPERV_R', 'LAYOUTS']
newfeaturenames = ['SYNCHRONY=', 'ALPHATHETA=', 'BETASMR=', 'TACTILE=', 'PERIPHDISPLAY=',
                   'ZSCORE=', '4-CHANNEL=', 'SUB-HZ=', 'FEATURE5=', 'FEATURE6=', 'AMPENABLES=', 'VERSION43=',
                   'VERSION44=', 'STUDY_EN', 'ADVMODES', 'FULLRECORD', 'SUPERV_R', 'LAYOUTS']


def handle_features(d, lns, info=None):
    # get build date
    # get expiration date
    # get list of dongles (dict for each dongle)
    # for each feature
    #    get yes/no
    #    see if already exists
    #    data is list [enab,build date, exp date,0,0]
    #
    bdate = None
    expdate = None
    extdate = None
    donglist = []
    for lv in lns:
        line = lv.strip()
        if line[:6] == 'BUILD=':
            bdate = int(line[6:])
        elif line[:8] == 'EXTDATE=':
            extdate = line[8:]
        elif line[:11] == 'EXPIRATION=':
            expdate = int(line[11:])
        elif line[:7] == 'DONGLE=':
            donglist.append(int(line[7:]))
        else:
            if extdate:
                expdate = extdate
                extdate = None
            for inx, feat in enumerate(features):
                i = line.find(feat)
                if i < 0:
                    continue
                ##                if feat == 'ZSCORE=' and filename:
                ##                    print line,"===",filename
                ##                    print '>>>>>>>',i,len(feat),line[i+len(feat):i+len(feat)]
                value = 0
                if line[i + len(feat):i + len(feat) + 1] == 'Y':
                    fval = 1
                else:
                    fval = 0
                if line[i:i + len(feat)] == 'AMPENABLES=':
                    fval = 1
                    try:
                        value = int(line[i + len(feat):i + len(feat) + 1])
                    except:
                        value = 0
                fname = newfeaturenames[inx][:-1]
                for dong in donglist:
                    dongdict = d.get(dong, {})
                    dval = dongdict.get(fname, [0, 0, 0, 0, 0, 0])
                    if dval[1] > bdate:
                        continue  # this file earlier than last build date
                    dval = [fval, bdate, expdate, value, 0, info]
                    dongdict[fname] = dval
                    d[dong] = dongdict
                break



"""

GAME ENABLES
LICENSEE=HPLself
BUILD=20100110
EXPIRATION=20101231
DONGLE=50024
DONGLE=50026
DONGLE=51695
GAME=8310, Space Race
REMOVE=8310, Space Race
GAME=8311, Chomper
GAME=8312, Boat Race
GAME=8320, StarLight (ESI)
GAME=8330, StarLight (original)
GAME=8321, StarCubes (ESI)
GAME=8331, StarCubes (original)
GAME=8321, Squared (NC)
GAME=8323, Kaleidoscape (NC)
GAME=8322, INtoIT (NC)
GAME=8324, StoneSoup (NC)
GAME=8350, Emotional Development
GAME=8351, Right Brain Exercise
GAME=8352, Perception Exercise
GAME=8353, Serenity
GAME=8354, Games for Adults
GAME=8355, Games for Kids
"""


def handle_games(d, lns, info=None):
    bdate = None
    expdate = None
    extdate = None
    donglist = []
    for lv in lns:
        line = lv.strip()
        if line[:6] == 'BUILD=':
            bdate = int(line[6:])
        elif line[:8] == 'EXTDATE=':
            extdate = line[8:]
        elif line[:11] == 'EXPIRATION=':
            expdate = int(line[11:])
        elif line[:7] == 'DONGLE=':
            donglist.append(int(line[7:]))
        elif line[:7] == 'REMOVE=' or line[:5] == 'GAME=':
            if line[0] == 'G':
                vals = line[5:].split(',')
            else:
                vals = line[7:].split(',')
                if len(vals) == 1:
                    vals = [vals[0], 'UNK?']
            code = vals[0]

            if extdate:
                expdate = extdate
                extdate = None
            for dong in donglist:
                dongdict = d.get(dong, {})
                dval = dongdict.get(code, [0, 0, 0, 0, 0, 0])
                if dval[1] > bdate:
                    continue  # this file earlier than last build date
                if line[0] == 'G':
                    fval = 1
                else:
                    fval = 0
                dval = [fval, bdate, expdate, code, vals[1].strip(), info]
                dongdict[code] = dval
                d[dong] = dongdict


def _options(lns, d, info):
    for lv in lns:
        line = lv.strip()
        if line == 'FEATURES' or line == 'VERSION':
            handle_features(d, lns, info)
            break

        if line == 'GAME ENABLES':
            handle_games(d, lns, info)
            break


def makefile(donglist, name, bdate, info, zd):
    # pass  # actually create files with newer replacing older
    # ddddd_LICENSE_bdate=ddddd_LICENSE.KEY
    # ddddd_DUPDATE_bdate=ddddd_DUPDATE.KEY
    # ddddd_name_bdate=ddddd_file
    # create ddddd_file if not exist else just point to file
    fparts = os.path.splitext(info.filename)
    fext = fparts[0] + '_' + fparts[1][1:]
    bd = int(bdate)
    dtx = datetime.datetime(*info.date_time)
    dt = dtx.timetuple()
    created_files = []

    timestup = (time.mktime(dt), time.mktime(dt))  # ATIME,MTIME
    for dong in donglist:
        n = '%05d_%s' % (dong, name)
        nfull = '%05d_%s_%s' % (dong, name, bdate)
        print ('searching with prefix ', n)
        bucket_objects = bucket.objects.filter(Prefix=n)
        files = []
        for obj in bucket_objects:
            print ('Found object named ', obj.key)
            files.append(obj.key)
        found = 0
        newname = '%s.%s' % (nfull, fext)
        for f in files:
            bn = os.path.splitext(os.path.basename(f))[0]
            fdate = int(bn[len(n) + 1:])
            # print f,bd,fdate
            if fdate < bd:
                print ('Deleting file name ', f)
                bucket.delete_objects(Delete={'Objects': [{'Key': f}]})
            else:
                found = 1
                continue

            created_files.append([newname, zd, str(time.mktime(dt))])

        if not found:
            created_files.append([newname, zd, str(time.mktime(dt))])

            # see if any such file exists
            #      no so just create it with the content and date/time
            # see if newer than existing
            #    no - ignore
            # delete old file and create new one

    return created_files


def process(info, zd):
    created_files = []
    lines = zd.split('\n')
    if info.filename == 'LICENSE.KEY':
        fout = _licefile(lines)
        bdate, expdate, kind, licto, donglist = fout
        created_files.extend(makefile(donglist, 'LICENSE', bdate, info, zd))
    elif info.filename == 'DUPDATE.KEY':
        fout = _licefile(lines)
        bdate, expdate, kind, licto, donglist = fout
        created_files.extend(makefile(donglist, 'DUPDATE', bdate, info, zd))
    else:
        if os.path.splitext(info.filename)[1].lower() != '.opt':
            return
        d = {}
        _options(lines, d, info)
        # now handle dictionary of items
        dongkeys = d.keys()
        dongkeys.sort()
        for dong in dongkeys:
            dongdict = d.get(dong, {})
            ddkeys = dongdict.keys()
            for code in ddkeys:
                dval = dongdict.get(code, [0, 0, 0, 0, 0, 0])
                dfval, dbdate, dexpdate, dcode, dvals, df = dval
                created_files.extend(makefile([dong, ], code, dbdate, df, zd))

    return created_files


# this is what creates the separate files from ekb files
def make_file_list(fname):
    """

    :rtype: Array
    """
    try:
        zf = zipfile.ZipFile(fname, 'r')
    except:
        return
    created_files = []
    zflist = zf.infolist()
    for info in zflist:
        if info.filename == 'LOG.TXT':
            continue
        zd = zf.read(info)
        created_files.extend(process(info, zd))

    zf.close()
    return created_files


# noinspection PyUnusedLocal
def python_handler(event, context):
    files_uploaded = 0
    for file_record in event['Records']:
        source_bucket = file_record['s3']['bucket']['name']
        key = urllib.unquote_plus(file_record['s3']['object']['key'])
        temp_key = uuid.uuid4()
        download_path = '/tmp/{}{}'.format(temp_key, key)
        print ('bucket, key, download', source_bucket, key, download_path)
        s3_client.Bucket(source_bucket).download_file(key, download_path)
        created_file_info = make_file_list(download_path)
        for created_file in created_file_info:
            if len(created_file) < 3:
                continue
            print ('uploading to bucket {} with key {} and timestamp {}'. \)
                format('keyprocess-processed', created_file[0], created_file[2])
            s3_client.Object('keyprocess-processed', created_file[0]).put(Body=created_file[1], Metadata={
                'x-eeger-timestamp': created_file[2]})
            files_uploaded += 1

    return files_uploaded