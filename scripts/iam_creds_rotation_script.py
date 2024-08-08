import json
import logging
import os
from datetime import datetime
 
import boto3
 
logging.basicConfig(level=logging.INFO)
 
LOGGER = logging.getLogger(__name__)
 

def save_creds(ssm_client, iam_user, access_key_id, secret):
	iam_key = "/{}/iam-key".format(iam_user)
	iam_secret = "/{}/iam-secret".format(iam_user)
	ssm_client.put_parameter(
		Name=iam_key, Value=access_key_id, Type="SecureString", Overwrite=True
	)
	ssm_client.put_parameter(
		Name=iam_secret, Value=secret, Type="SecureString", Overwrite=True
	)
	output = {"iam_key": access_key_id, "iam_secret": secret}
	output_json = json.dumps(output, indent=2)
	print(output_json)
 

def is_key_outdated(key, max_age_days):
	today = datetime.now()
	creation_timestamp = datetime.fromisoformat(
		str(key["CreateDate"])
	).replace(tzinfo=None)
	diff_date = today - creation_timestamp
	return diff_date.days > int(max_age_days)
 

def create_new_key(iam_client, iam_user, ssm_client):
	new_key = iam_client.create_access_key(UserName=iam_user)
	if new_key:
		new_key = new_key["AccessKey"]
		save_creds(
			ssm_client,
			iam_user,
			new_key["AccessKeyId"],
			new_key["SecretAccessKey"],
	   )
		return new_key
	else:
		LOGGER.error("Couldn't create a key for the user:", iam_user)
 

def deactivate_key(iam_client, iam_user, key):
	iam_client.update_access_key(
		UserName=iam_user, AccessKeyId=key["AccessKeyId"], Status="Inactive"
	)
 

def delete_key(iam_client, ssm_client, iam_user, key):
	iam_client.delete_access_key(
		UserName=iam_user, AccessKeyId=key["AccessKeyId"]
	)
	deactivated_key_timestamp = "/{}/deactivated-key-timestamp".format(
		iam_user
	)
	ssm_client.put_parameter(
		Name=deactivated_key_timestamp,
		Value="-1",
		Type="String",
		Overwrite=True,
	)
 

def save_deactivation_timestamp_to_ssm(ssm_client, iam_user):
	deactivated_key_timestamp = "/{}/deactivated-key-timestamp".format(
		iam_user
	)
	ssm_client.put_parameter(
		Name=deactivated_key_timestamp,
		Value=str(datetime.now()),
		Type="String",
		Overwrite=True,
	)
 

def is_inactive_key_outdated(ssm_client, iam_user, delete_after_days):
	today = datetime.now()
	deactivation_timestamp = get_deactivation_timestamp_from_ssm(
		ssm_client, iam_user
	)
	diff_date = today - deactivation_timestamp
	return diff_date.days > int(delete_after_days)
 

def get_deactivation_timestamp_from_ssm(ssm_client, iam_user):
	deactivated_key_timestamp = "/{}/deactivated-key-timestamp".format(
		iam_user
	)
	get_response = ssm_client.get_parameter(
		Name=deactivated_key_timestamp, WithDecryption=True
	)
	value = get_response["Parameter"]["Value"]
	if value == "-1":
		LOGGER.error(
			"No dectivation timestamp for the old key for the user: %s",
			iam_user,
		)
		return value
	return datetime.fromisoformat(str(value)).replace(tzinfo=None)
 

def get_active_keys(keys):
	return [key for key in keys if key["Status"] == "Active"]
 

def get_inactive_keys(keys):
	return [key for key in keys if key["Status"] == "Inactive"]
 

def populate_last_access_for_keys(iam_client, keys):
	for key in keys:
		last_used_meta_data = iam_client.get_access_key_last_used(
			AccessKeyId=key["AccessKeyId"]
		)
		if "LastUsedDate" in last_used_meta_data["AccessKeyLastUsed"]:
			key["LastUsedDate"] = last_used_meta_data["AccessKeyLastUsed"][
				"LastUsedDate"
			]
		else:
			return False
	return True
 

def get_recently_created_key(key1, key2):
	key1_create_date = datetime.fromisoformat(str(key1["CreateDate"]))
	key2_create_date = datetime.fromisoformat(str(key2["CreateDate"]))
	return key1 if key1_create_date > key2_create_date else key2
 

def get_recently_used_key(key1, key2):
	key1_last_used_date = datetime.fromisoformat(str(key1["LastUsedDate"]))
	key2_last_used_date = datetime.fromisoformat(str(key2["LastUsedDate"]))
	return key1 if key1_last_used_date > key2_last_used_date else key2
 

def rotate_iam_credentials(
	iam_user,
	access_key_id,
	secret_key,
	region,
	max_age_in_days=60,
	delete_after_in_days=10,
):
	# Create IAM client
	iam_client = boto3.client("iam")
 
	# Create SSM client
	ssm_client = boto3.client("ssm", region_name=region)
 
	# List access keys
	keys_metadata = iam_client.list_access_keys(UserName=iam_user)
	keys = keys_metadata["AccessKeyMetadata"]
	if keys:
		# Populate the meta-data with the last access date for each key
		all_keys_used = populate_last_access_for_keys(iam_client, keys)
		active_keys = get_active_keys(keys)
		# If there is multiple active keys and they are all used before
		if len(active_keys) == 2 and all_keys_used:
			recently_created_key = get_recently_created_key(keys[0], keys[1])
			recently_used_key = get_recently_used_key(keys[0], keys[1])
			if (
				recently_created_key["AccessKeyId"]
				== recently_used_key["AccessKeyId"]
			):
				older_key = [
					key
					for key in keys
					if key["AccessKeyId"]
					!= recently_created_key["AccessKeyId"]
				][0]
				deactivate_key(iam_client, iam_user, older_key)
				save_deactivation_timestamp_to_ssm(ssm_client, iam_user)
 
		# If there is only one key and is outdated
		elif len(keys) == 1 and is_key_outdated(keys[0], max_age_in_days):
			return create_new_key(iam_client, iam_user, ssm_client)
 
		# If there is one active key and one inactive key
		elif len(keys) > len(active_keys):
			if is_inactive_key_outdated(
				ssm_client, iam_user, delete_after_in_days
			):
				inactive_key = get_inactive_keys(keys)[0]
				delete_key(iam_client, ssm_client, iam_user, inactive_key)
 
		save_creds(ssm_client, iam_user, access_key_id, secret_key)
	else:
		# current iam_user has 0 access key. Create one now.
		return create_new_key(iam_client, iam_user, ssm_client)
 

if __name__ == "__main__":
	input_params = {
		"iam_user": os.getenv("iam_user"),
		"access_key_id": os.getenv("access_key_id"),
		"secret_key": os.getenv("secret_key"),
		"max_age_in_days": os.getenv("max_age_in_days"),
		"delete_after_in_days": os.getenv("delete_after_in_days"),
		"region": os.getenv("region"),
	}
	rotate_iam_credentials(**input_params)