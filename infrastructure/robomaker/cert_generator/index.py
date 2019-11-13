import boto3
import cfnresponse
import os, json, logging

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

s3 = boto3.client('s3')
iot = boto3.client('iot')

def lambda_handler(event, context):
  LOGGER.info('Event Received:\n%s', json.dumps(event))

  responseStatus = cfnresponse.SUCCESS
  responseData = {}
  physicalResourceId = event['PhysicalResourceId'] if 'PhysicalResourceId' in event else None

  try:
    properties = event['ResourceProperties']

    thingArn = properties.get('ThingArn', None)
    if thingArn is None or len(thingArn) <= 0:
      raise Exception('ThingArn must not be None or empty.')

    robotName = properties.get('RobotName', thingArn.split('thing/')[1])
    bucketName = os.getenv('BucketName')
    keyPrefix = os.getenv('KeyPrefix') + robotName + '_'

    requestType = event['RequestType']
    if requestType == 'Create' or requestType == 'Update':
      result = create_cert_and_keys()
      certShortId = result['CertId'][0:10]
      keyPrefix = keyPrefix + certShortId + '/'
      files = result['Files']

      for index in files:
        file = files[index]
        key = keyPrefix + file['Name'].replace('certId', certShortId)
        save_file(bucketName, key, file['Content'])
        if file['Output']:
          responseData[index] = create_presigned_url(bucketName, key)

      config = create_config(certShortId, thingArn)
      configKey = keyPrefix + 'config.json'
      save_file(bucketName, configKey, json.dumps(config, indent = 4, sort_keys = True))
      responseData['Config'] = create_presigned_url(bucketName, configKey)

      physicalResourceId = result['CertId']
      responseData['CertificateArn'] = result['CertArn']
    elif requestType == 'Delete':
      if physicalResourceId == None:
        raise ValueError('Unable to get PhysicalResourceId, which is required for deletion.')

      iot.update_certificate(certificateId = physicalResourceId, newStatus = 'INACTIVE')
      iot.delete_certificate(certificateId = physicalResourceId, forceDelete = True)

      keyPrefix = keyPrefix + physicalResourceId[0:10] + '/'
      files = s3.list_objects_v2(Bucket = bucketName, Prefix = keyPrefix)['Contents']
      for file in files:
        s3.delete_object(Bucket = bucketName, Key = file['Key'])
    else:
      raise ValueError('Unsupported request type "{0}".'.format(requestType))
  except Exception as ex:
    responseStatus = cfnresponse.FAILED
    LOGGER.error(ex)

  cfnresponse.send(event, context, responseStatus, responseData, physicalResourceId)

def create_cert_and_keys():
  response = iot.create_keys_and_certificate(setAsActive = True)
  return {
    'CertArn': response['certificateArn'],
    'CertId': response['certificateId'],
    'Files': {
      'Certificate': {
        'Name': 'certId.cert.pem',
        'Content': response['certificatePem'],
        'Output': True
      },
      'PublicKey': {
        'Name': 'certId.public.key',
        'Content': response['keyPair']['PublicKey'],
        'Output': False
      },
      'PrivateKey': {
        'Name': 'certId.private.key',
        'Content': response['keyPair']['PrivateKey'],
        'Output': True
      }
    }
  }

def create_config(certShortId, thingArn):
  iotHost = iot.describe_endpoint(endpointType = 'iot:Data-ATS')['endpointAddress']
  return {
    'coreThing': {
      'caPath': 'AmazonRootCA1.pem',
      'certPath': '{0}.cert.pem'.format(certShortId),
      'ggHost': 'greengrass-ats.iot.{0}.amazonaws.com'.format(os.getenv('AWS_REGION')),
      'iotHost': iotHost,
      'keepAlive': 600,
      'keyPath': '{0}.private.key'.format(certShortId),
      'thingArn': thingArn
    },
    'crypto': {
      'caPath': 'file:///greengrass/certs/AmazonRootCA1.pem',
      'principals': {
        'IoTCertificate': {
          'CertificatePath': 'file:///greengrass/certs/{0}.cert.pem'.format(certShortId),
          'PrivateKeyPath': 'file:///greengrass/certs/{0}.private.key'.format(certShortId)
        },
        'SecretsManager': {
          'PrivateKeyPath': 'file:///greengrass/certs/{0}.private.key'.format(certShortId)
        }
      }
    },
    'managedRespawn': False,
    'runtime': {
      'allowFunctionsToRunAsRoot': 'yes',
      'cgroup': {
        'useSystemd': 'yes'
      }
    }
  }

def save_file(bucketName, key, content):
  s3.put_object(Bucket = bucketName, Key = key, Body = content)

def create_presigned_url(bucketName, key, expiration = 3600):
  return s3.generate_presigned_url(ClientMethod = 'get_object', Params = { 'Bucket': bucketName, 'Key': key }, ExpiresIn = expiration)
