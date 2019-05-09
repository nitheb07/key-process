"""
decipher .ekx file


"""
import base64
import datetime
import json
import os
import os.path
import uuid
import zipfile
import boto3
import sys

s3_resource = boto3.resource('s3')
bucket = s3_resource.Bucket('keyprocess-processed')
user_bucket = s3_resource.Bucket('keyprocess-user-downloads')


def rot48x(instr):
    out_string = ''
    for c in instr:
        cv = ord(c)
        if 32 <= cv < 128:
            cv = (cv - 32 + 48) % 96 + 32
        out_string += chr(cv)
    return out_string


def get_request(file_data, check):
    file_list = file_data.split('\n')

    # validate date stuff
    saved_time = rot48x(file_list[0].strip())
    sv = int(saved_time)
    file_time_now = datetime.datetime.utcnow().strftime('%Y%m%d%H%M')
    ftd = int(file_time_now)
    if sv > ftd:
        # lie-file was built in future
        return 'Bad date', None
    # TODO fix this back to a reasonable time frame
    if ftd - sv > 40000000:
        # print file_time_now,saved_time
        return 'File too old', None  # too old

    # check format and get dongle number
    if file_list[1][:7] != "DONGLE=":
        return 'Format bad 1', None
    dongle_number = file_list[1][7:].strip()
    if file_list[2][:8] != 'DUPDATE=':
        return 'Format bad 2', None
    dupdate = file_list[2][8:].strip()
    if file_list[3][:11] != 'Build Date=':
        return 'Format bad 3', None
    build_date = file_list[3][11:].strip()
    check.append((dongle_number, 'LICENSE', build_date, 'LICENSE.KEY'))
    if dupdate != '':
        check.append((dongle_number, 'DUPDATE', dupdate, 'DUPDATE.KEY'))
    # unpack information
    v440 = 0
    for ln in file_list[4:]:
        # print ln
        parts = ln.strip().split('|')
        if len(parts) != 2:
            continue
        pieces = parts[0].split(' ')
        # print 'pieces',pieces
        if pieces[0].strip() == 'VERSION':
            v440 = 1
        # 0 is 'name' of option
        bld = parts[0].find('Built=')
        if bld < 0:
            continue
        built = parts[0][bld + 6:bld + 14]

        check.append((dongle_number, pieces[0].strip(), built.strip(), parts[1].strip()))  # only latest version

    if v440 == 0:
        return 'Not supported until 440', None

    return None, dongle_number


def new_ekb(dongle, destination, check):
    dongle_number = int(dongle)
    prefix = '%05d' % dongle_number
    bucket_objects = bucket.objects.filter(Prefix=prefix)
    file_list = []
    for obj in bucket_objects:
        #print 'Found object named', obj.key
        file_list.append(obj.key)

    file_finder = [0] * len(file_list)
    for file_index, file_name in enumerate(file_list):  # this is what is on key store folder for the specified dongle
        # print dongle,file_index,file_name
        file_finder[file_index] = 1
        split_name = os.path.basename(file_name).split('_')
        for item in check:  # this is what was in the old key folder on EEGer
            dong, name, build_date, file_code = item
            if name == split_name[1]:
                bn = os.path.splitext(os.path.basename(file_name))[0]
                finder = '%05d_%s' % (dongle_number, name)
                file_date = int(bn[len(finder) + 1:])  # date of file in store folder
                if build_date == 'None' or int(file_date) > int(build_date):
                    file_finder[file_index] = 2
                else:
                    file_finder[file_index] = 0  # don't need this one

    # now to make a new one
    number_of_files = 0
    line_data = {}
    temp_directory = "{}{}/".format(destination,uuid.uuid4())
    if not os.path.exists(temp_directory):
        os.makedirs(temp_directory)

    for file_index, file_name in enumerate(file_list):
        if file_finder[file_index]:
            download_file_name = os.path.join(temp_directory, file_name)
            file_object = s3_resource.Object('keyprocess-processed', file_name)
            # download the files from s3 for processing
            file_object.download_file(download_file_name)
            file_parts = os.path.splitext(os.path.basename(download_file_name))[1][1:].split('_')
            t_val = float(file_object.metadata['x-eeger-timestamp'])
            fd = open(download_file_name, 'r')
            file_data = fd.read()
            fd.close()
            destination_name = '%s.%s' % (file_parts[0], file_parts[1])
            line_data[destination_name] = (file_data, t_val)
            number_of_files += 1

    if number_of_files == 0:
        return None, None

    file_time_now = datetime.datetime.utcnow().strftime('%Y%m%d%H%M')
    destination_file_name = '%05d_%s.EKB' % (dongle_number, file_time_now)
    line_data_keys = line_data.keys()
    line_data_keys.sort()
    final_location = os.path.join(destination, destination_file_name)
    zf = zipfile.ZipFile(final_location, 'w',
                         zipfile.ZIP_DEFLATED)
    for file_name in line_data_keys:
        file_data, t_val = line_data[file_name]
        dtm = datetime.datetime.fromtimestamp(t_val)
        zi = zipfile.ZipInfo(file_name, dtm.timetuple())
        zf.writestr(zi, file_data)
    zf.close()
    return destination_file_name, final_location


def check_new_files(file_data, destination):
    check = []
    ans, dong = get_request(file_data, check)
    if ans is not None:
        return {'code': 'error', "message": ans}  # error message
    if len(check) == 0:
        return {'code': 'error', "message": "Request file was empty"}
    file_name, local_file_location = new_ekb(dong, destination, check)
    if local_file_location and file_name:
        data = open(local_file_location, 'r')
        s3_resource.Object('keyprocess-user-downloads', file_name).put(Body=data)
        object_url = boto3.client('s3').generate_presigned_url(
            ClientMethod='get_object',
            Params={
                'Bucket': 'keyprocess-user-downloads',
                'Key': file_name
            }
        )
        return {'code': 'new', 'message': object_url}
    else:
        return {'code': 'ok', 'message': 'Up to date'}


# noinspection PyUnusedLocal
def lambda_handler(event, context):
    message = base64.b64decode(event['message'])
    out_string = []
    for index, val in enumerate(message.split('\n')):
        out_string.append(base64.b64decode(val))
    combined_string = '\n'.join(str(x) for x in out_string)
    return check_new_files(combined_string, '/tmp/')


if __name__ == "__main__":
    try:
        zf = zipfile.ZipFile(sys.argv[1], 'r')
    except IOError as e:
        print ("Error finding file ", e)
        raise
    except Exception as e:
        print ('Error opening zip file', e)
        raise

    file_data = zf.read('KeyRequest.txt')
    zf.close()
    print (check_new_files(file_data, sys.argv[2]))
