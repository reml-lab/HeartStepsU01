import numpy as np
import pandas as pd
import datetime as dt
import os
import zipfile
from datetime import datetime, timedelta
from urllib.parse import urlparse

study_prefix = "U01"

def get_user_id_from_filename(f):
    #Get user id from from file name
    return(f.split(".")[3])

def get_file_names_from_zip(z, file_type=None, prefix=study_prefix):  
    #Extact file list
    file_list = list(z.filelist)
    if(filter is None):
        filtered = [f.filename for f in file_list if (prefix in f.filename) and (".csv" in f.filename)]
    else:
        filtered = [f.filename for f in file_list if (file_type in f.filename and prefix in f.filename)]
    return(filtered)

def get_data_catalog(catalog_file, data_file, data_dir, dict_dir):
  dc=pd.read_csv(catalog_file)
  dc=dc.set_index("Data Product Name")
  dc.data_file=data_dir+data_file #add data zip file field
  dc.data_dir=data_dir #add data zip file field
  dc.dict_dir=dict_dir #add data distionary directory field
  return(dc)

def get_data_dictionary(data_catalog, data_product_name):
    dictionary_file = data_catalog.dict_dir + data_catalog.loc[data_product_name]["Data Dictionary File Name"]
    dd=pd.read_csv(dictionary_file)
    dd=dd.set_index("ElementName")
    dd.data_file_name = data_catalog.loc[data_product_name]["Data File Name"] #add data file name pattern field
    dd.name = data_product_name #add data product name field
    dd.index_fields = data_catalog.loc[data_product_name]["Index Fields"] #add index fields
    dd.description = data_catalog.loc[data_product_name]["Data Product Description"]
    return(dd)

def get_df_from_zip(file_type,zip_file, participants):
    
    #Get participant list from participants data frame
    participant_list = list(participants["Participant ID"])

    #Open data zip file
    z = zipfile.ZipFile(zip_file)
    
    #Get list of files of specified type
    file_list = get_file_names_from_zip(z, file_type=file_type)
    
    #Open file inside zip
    dfs=[]
    for file_name in file_list:
        sid = get_user_id_from_filename(file_name)
        if(sid in participant_list):
            f = z.open(file_name)
            file_size = z.getinfo(file_name).file_size
            if file_size > 0:
                df  = pd.read_csv(f, low_memory=False)
                df["Subject ID"] = sid
                dfs.append(df)
            else:
                print('warning %s is empty (size = 0)' % file_name)
    df = pd.concat(dfs)
    return(df)

def fix_df_column_types(df, dd):
    #Set Boolean/String fields to string type to prevent
    #interpretation as numeric for now. Leave nans in to
    #indicate missing data.
    for field in list(df.keys()):
        if not (field in dd.index): continue
        dd_type = dd.loc[field]["DataType"]    
        if dd_type in ["Boolean","String","Categorical"]:
            if field == 'url':
                urls = df[field].values
                for index, url in enumerate(urls):
                    parsed = urlparse(url)
                    df[field].values[index] = parsed.path[1:]
            else:
                df[field] = df[field].map(lambda x: x if str(x).lower()=="nan" else str(x))   
        elif dd_type in ["Ordinal"]:
            df[field] = df[field].map(lambda x: x if str(x).lower()=="nan" else int(x))
        elif dd_type in ["Time"]:
            df[field] = df[field].map(lambda x: x if str(x).lower()=="nan" else pd.to_timedelta(x))
        elif dd_type in ["Date"]:
            df[field] = df[field].map(lambda x: x if str(x).lower()=="nan" else datetime.strptime(x, "%Y-%m-%d"))   
        elif dd_type in ["DateTime"]:
            #Keep only time for now
            max_length = max([len(str(x).split(':')[-1]) for x in df[field].values]) # length of last item after ':'
            if max_length < 6: # this includes time with AM/PM
                df[field] = df[field].map(lambda x: x if str(x).lower()=="nan" else pd.to_timedelta(x[11:]))
            else: # for example: 2020-06-12 23:00:1592002802
                df[field] = df[field].map(lambda x: x if str(x).lower()=="nan" else
                                          pd.to_timedelta(pd.to_datetime(x[:16]).strftime("%H:%M:%S")))  
            #print('\n%s nlargest(10) =\n%s' % (field, df[field].value_counts().nlargest(10)))
    return(df)

def get_participant_info(data_catalog):
    file = data_catalog.data_dir + data_catalog.loc["Participant Information"]["Data File Name"]
    df   = pd.read_csv(file)
    return(df)

def get_participants_by_type(data_catalog, participant_type):
    pi = get_participant_info(data_catalog)
    pi = pi[pi["Participant Type"]==participant_type]
    return(pi)

def crop_data(participants_df, df, b_display, b_crop_end=True):
    #Crop before the intervention start date
    #Set b_crop_end = True to also crop after the end date (for withdrew status)
    participants_df = participants_df.set_index("Participant ID")
    fields = list(df.keys())
    #Create an observation indicator for an observed value in any
    #of the above fields. Sort to make sure data frame is in date order
    #per participant
    obs_df = 0+((0+~df[fields].isnull()).sum(axis=1)>0)
    obs_df.sort_index(axis=0, inplace=True,level=1)
    #Get the participant ids according to the data frame
    participants = list(obs_df.index.levels[0])
    frames = []
    for p in participants:
        intervention_date = participants_df.loc[p]['Intervention Start Date']
        dates = pd.to_datetime(obs_df[p].index)
        #Check if there is any data for the participant
        if(len(obs_df[p]))>0:
            new_obs_df = obs_df[p].copy()
            if str(intervention_date).lower() != "nan":
                #Check if intervention date is past today's date
                intervention_date = pd.to_datetime(intervention_date)
                new_obs_df = new_obs_df.loc[dates >= intervention_date]
                dates = pd.to_datetime(new_obs_df.index)
                today = pd.to_datetime(dt.date.today())
                if (intervention_date > today) and b_display:
                  print('{:<3} intervention date {} is past today\'s date {}'.format(
                          p, intervention_date.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d')))
                #Crop before the intervention start date
                dates_df = pd.to_datetime(df.loc[p].index)
                new_df = df.loc[p].copy()
                new_df = new_df.loc[dates_df >= intervention_date]
                if b_crop_end:
                    status = participants_df.loc[p]["Participant Status"]
                    end_date = participants_df.loc[p]['End Date']                    
                    if status == 'withdrew':
                        end_date = pd.to_datetime(end_date)
                        dates_df = pd.to_datetime(new_df.index)
                        new_df = new_df.loc[dates_df <= end_date]
                new_df['Subject ID'] = p
                new_df = new_df.reset_index()
                new_df['Date'] = pd.to_datetime(new_df['Date']).dt.strftime('%Y-%m-%d')
                new_df = new_df.set_index(['Subject ID', 'Date'])
                frames.append(new_df)
            else:
                if b_display:
                    status = participants_df.loc[p]["Participant Status"]
                    if (status != 'withdrew') and (str(status).lower() != 'nan'): 
                        print('{:<3} ({}) missing intervention start date'.format(p, status))
                continue
    if len(frames) > 0:
        df = pd.concat(frames)
        df = df.sort_index(level=0)
    return df

def crop_end_fitbit_per_minute(data_product, participants_df, df, b_display):
    #For Fitbit Data Per Minute, we only crop after the end date (for withdrew status)
    #Fitbit Data Per Minute has 'Subject ID', 'time' as indices and 'date' as column
    participants_df = participants_df.set_index("Participant ID")
    fields = list(df.keys())
    initial_indices = df.index.names
    #Create an observation indicator for an observed value in any
    #of the above fields. Sort to make sure data frame is in date order
    #per participant
    obs_df = 0+((0+~df[fields].isnull()).sum(axis=1)>0)
    obs_df.sort_index(axis=0, inplace=True,level=1)
    #Get the participant ids according to the data frame
    participants = list(obs_df.index.levels[0])
    frames = []
    for p in participants:
        #Check if there is any data for the participant
        if(len(obs_df[p]))>0:
            new_df = df.loc[p].copy()
            date_name = ''
            if 'Date' in new_df:
                date_name = 'Date'
            elif 'date' in new_df:
                date_name = 'date'
            if date_name != '':        
                status = participants_df.loc[p]["Participant Status"]
                if status == 'withdrew':
                    new_df[date_name] = pd.to_datetime(new_df[date_name])
                    end_date = pd.to_datetime(participants_df.loc[p]['End Date'])
                    new_df = new_df.loc[new_df[date_name] <= end_date]
                    new_df[date_name] = new_df[date_name].dt.strftime('%Y-%m-%d')
                    if (b_display):
                        print('%s: cropped after %s for withdrew participant %s' % (
                               data_product, end_date.strftime('%Y-%m-%d'), str(p)))
            new_df['Subject ID'] = p
            new_df = new_df.reset_index()
            new_df = new_df.set_index(initial_indices)            
            frames.append(new_df)
    if len(frames) > 0:
        df = pd.concat(frames)
        df = df.sort_index(level=0)
        if (b_display):
            print('\nchecking data types...\n')
    return df

def load_data(data_catalog, data_product, b_crop=True, b_display=True):
    participant_df  = get_participants_by_type(data_catalog,"full")
    data_dictionary = get_data_dictionary(data_catalog, data_product)    
    df = get_df_from_zip(data_dictionary.data_file_name, data_catalog.data_file, participant_df)
    index = [x.strip() for x in data_dictionary.index_fields.split(";")]
    df = df.set_index(index)
    df = df.sort_index(level=0)    
    if (b_crop) and (data_product != 'Fitbit Data Per Minute'):        
        df = crop_data(participant_df, df, b_display, b_crop_end=True)
    elif (b_crop) and (data_product == 'Fitbit Data Per Minute'):
        df = crop_end_fitbit_per_minute(data_product, participant_df, df, b_display)
    df = fix_df_column_types(df,data_dictionary)
    df.name = data_dictionary.name   
    return(df)

def load_baseline(data_catalog, data_product, filename):
    data_dictionary = get_data_dictionary(data_catalog, data_product)
    df = pd.read_csv(filename)    
    index = [x.strip() for x in data_dictionary.index_fields.split(";")]
    df = df.set_index(index)
    df = fix_df_column_types(df,data_dictionary)
    df.sort_index(level=0)
    df.name = data_dictionary.name
    return(df)
        
def get_subject_ids(df, b_isbaseline=False):
    if b_isbaseline:
        sids = df.index.astype(str)
    else:
        sids = list(df.index.levels[0])    
    return list(sids)

def get_variables(df): 
    numerical_types = [np.dtype('int64'), np.dtype('float64')]
    cols = [c for c in list(df.columns) if df.dtypes[c] in numerical_types]
    return(cols)

def get_catalogs(catalog_file):
    df = pd.read_csv(catalog_file)
    df = df["Data Product Name"]
    df = df[df.values != "Participant Information"]
    df = df[df.values != "Baseline Survey"]
    return list(df)

def get_categories(dd, field):
    categories = dd.loc[field]['Notes'].split(' | ')
    return categories

def resample_fitbit_per_minute(participant='105', df=None, filename=None, interval='30Min', b_dropna=True):
    #1. Set df to desired input df, or set filename to load df (df=None)
    #2. Set participant ID, for example: '105'
    #3. Set interval for resampling, for example: '30Min'
    if filename != None:
        print('loading data for participant %s from %s' % (participant, filename))
        df = pd.read_csv(filename, low_memory=False)
    else:
        print('getting data for participant', participant)
        df = df.reset_index()
    df = df.groupby(by='Subject ID').get_group(participant)
    #Temporary fix for data export issue: replace S with 00 in time format
    df['time'] = df['time'].map(lambda x: str(x).replace('S', '00'))
    df['datetime'] = df['date'].astype(str) + ' ' + df['time'].astype(str)
    df['datetime'] = pd.to_datetime(df['datetime'], format='%Y-%m-%d %H:%M:%S')
    df = df.set_index('datetime')
    df = df.resample(interval, level=0).first()
    df = df.reset_index().set_index(['Subject ID', 'time'])
    df.sort_index(level=0)
    df.name = 'Fitbit Data Per Minute'
    if b_dropna:
        df = df.dropna()
    return df


