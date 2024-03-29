import pandas as pd
import numpy as np
import collections
import sys, getopt
import os
from os import path

def process_baseline_survey(data_dictionary_filename, data_filename, output_data_folder, output_data_dictionary_folder):

    print('input dd    =', data_dictionary_filename)
    print('input df    =', data_filename)
    print('output data dir  =', output_data_folder)
    print('output data dictionary dir  =', output_data_dictionary_folder)
    
    #--------------------------------------------------------------------------------
    #Process data dictionary for U01DataDictionaries
    
    dd = pd.read_csv(data_dictionary_filename)

    dd = dd[dd['Form Name'] == 'baseline_survey_2']

    map_to_new_name = pd.Series(dd['New Name'].values, index=dd['Variable / Field Name']).to_dict()
    
    dd['Field Type'] = np.where((dd['Text Validation Type OR Show Slider Number'] == 'number'), 'Integer', dd['Field Type'])
    
    dd = dd[['Variable / Field Name', 'Field Type', 'Field Label', 'Choices, Calculations, OR Slider Labels']]
    dd = dd.rename(columns={'Variable / Field Name': 'ElementName',
                            'Field Type': 'DataType',
                            'Field Label': 'ElementDescription',
                            'Choices, Calculations, OR Slider Labels':'Notes'})
    dd.insert(2, 'Size', '')
    dd.insert(3, 'Required', 'Required') 
    dd.insert(5, 'ValueRange', '')
    dd.insert(7, 'Aliases', '')
    dd['DataType'] = dd['DataType'].replace('radio','Categorical')
    dd['DataType'] = dd['DataType'].replace('dropdown','Categorical')
    dd['DataType'] = dd['DataType'].replace('yesno','Boolean')
    #Remove remaining text that are not number
    dd = dd[dd['DataType'] != 'text']
    dd = dd[dd['DataType'] != 'descriptive']
    dd = dd[dd['DataType'] != 'notes']

    dd['ElementDescription'] = [str(x).replace('[SELECT ALL THAT APPLY]', '(check all that apply)') for x in dd['ElementDescription']]
    dd['ElementDescription'] = [str(x).replace('(Please check all that apply to you)', '(Check all that apply)') for x in dd['ElementDescription']]
    dd['Notes'] = [str(x).replace(' (list which ones below)', '') for x in dd['Notes']]
     
    #Expand checkbox and set to Boolean
    dd_checkbox = dd[dd['DataType'] == 'checkbox']['ElementName']
    for index, item in enumerate(dd['ElementName'].values):
        for element_name in dd_checkbox:
            if item == element_name:
                notes = str(dd['Notes'].values[index]).split('|')
                notes = [str(x).strip() for x in notes]
                for expand, item in enumerate(notes):
                    item = item.split(',')
                    key = int(item[0])
                    value = str(item[1]).strip()                
                    new_name = element_name + ': ' + value
                    new_name = new_name.replace('(specify below)','').strip()
                    new_index = index + expand
                    line = pd.DataFrame({'ElementName': new_name, 'DataType': 'Boolean', 'Required': 'Required',
                                         'ElementDescription': new_name}, index=[new_index])
                    dd = dd.append(line, ignore_index=False)

    
    #--------------------------------------------------------------------------------
    #Process data for U01Data

    df = pd.read_csv(data_filename)
    
    df = df.drop(columns=['baseline_survey_2_complete'])
    
    dd_categorical = dd[dd['DataType'] == 'Categorical']['ElementName']
    dd_binary = dd[dd['DataType'] == 'Boolean' ]['ElementName']

    for field in list(df.keys()):        
        pos = field.find('___')
        if pos > 0:
            #Get the checkbox value after '___'
            #shorten_field is the corresponding checkbox name
            checkbox = int(field[pos+3:])
            shorten_field = str(field)[:pos]
            dict_notes = {}
            for index, item in enumerate(dd['ElementName'].values):
                if item == shorten_field:
                    notes = str(dd['Notes'].values[index]).split('|')
                    notes = [str(x).strip() for x in notes]
                    current_value = ''
                    for item in notes:
                        item = item.split(',')                
                        key = int(item[0])
                        value = str(item[1]).strip()
                        if checkbox == key:
                            current_value = value
                        if key == 0:
                            dict_notes[key] = str(key) + ': No'
                        else:
                            dict_notes[key] = str(key) + ': Yes'
                    break
            new_name = shorten_field + ': ' + current_value
            new_name = new_name.replace('(specify below)','').strip()
            df = df.rename(columns={field: new_name})
            df[new_name] = df[new_name].map(lambda x: x if str(x).lower()=="nan" else dict_notes[int(x)])

        if field in dd_binary.values:
            dict_notes = {0: '0: No', 1: '1: Yes'}
            df[field] = df[field].map(lambda x: x if str(x).lower()=="nan" else dict_notes[int(x)])

        if field in dd_categorical.values:
            dict_notes = {}
            for index, item in enumerate(dd['ElementName'].values):
                if item == field:
                    notes = str(dd['Notes'].values[index]).split('|')
                    notes = [str(x).strip() for x in notes]
                    current_value = ''
                    for item in notes:
                        item = item.split(',')                
                        key = int(item[0])
                        value = str(item[1]).strip()
                        dict_notes[key] = str(key) + ': ' + value.strip()
                    dd['Notes'].values[index] = ' | '.join(list(dict_notes.values()))
                    break                
            df[field] = df[field].map(lambda x: x if str(x).lower()=="nan" else dict_notes[int(x)])


    #--------------------------------------------------------------------------------
    #Create new csv files
    
    #Remove checkbox from data dictionary, after expanding the checkbox data
    dd = dd[dd['DataType'] != 'checkbox']

    #Replace with new name
    def shorten(x):
        return str(x.split(':')[0]) 
    dd['ElementName'] = dd['ElementName'].map(lambda x: x.replace(shorten(x), map_to_new_name[shorten(x)]))
    dd['ElementDescription'] = dd['ElementDescription'].map(lambda x: x.replace(shorten(x), map_to_new_name[shorten(x)])
                                                            if shorten(x) in map_to_new_name else x)    
    df.columns = df.columns.map(lambda x: x.replace(shorten(x), map_to_new_name[shorten(x)])
                                                            if shorten(x) in map_to_new_name else x)

    df = df.rename(columns={'sex': 'gender'})
    df['gender'] = df['gender'].map(lambda x: "0: Female" if str(x)=="0" else "1: Male")
    new_frame = pd.DataFrame([['gender', 'Boolean', 'Required', 'Gender of the participant (0: Female, 1: Male)']],
                             columns=['ElementName','DataType','Required', 'ElementDescription'])
    dd = pd.concat([new_frame, dd])
    
    output_data_dictionary = 'baseline-survey.csv'
    output_data = 'baseline-survey-data.csv'
    output_data_dictionary_path = os.path.join(output_data_dictionary_folder, output_data_dictionary)
    output_data_path = os.path.join(output_data_folder, output_data)
    dd.to_csv(output_data_dictionary_path, index=False)
    df.to_csv(output_data_path, index=False)

    print('dd shape    =', dd.shape)
    print('df shape    =', df.shape)
    print('dd output   =', output_data_dictionary)
    print('df output   =', output_data)

    #--------------------------------------------------------------------------------
    #Create TIPI scores

    df_data = {}

    for name in list(df.columns):
        if str(name).lower().find('tipi') != -1:
            df_data[name] = df[name]

    reverse_map = { '0: 1 = Disagree strongly'          : '6: 7 = Agree strongly',
                    '1: 2 = Disagree moderately'        : '5: 6 = Agree moderately',
                    '2: 3 = Disagree a little'          : '4: 5 = Agree a little',
                    '3: 4 = Neither agree nor disagree' : '3: 4 = Neither agree nor disagree',
                    '4: 5 = Agree a little'             : '2: 3 = Disagree a little',
                    '5: 6 = Agree moderately'           : '1: 2 = Disagree moderately',
                    '6: 7 = Agree strongly'             : '0: 1 = Disagree strongly' }
    
    def reverse(input_df):
        ouput_df = input_df.copy()
        for i, x in enumerate(ouput_df):
            if str(x).lower()=='nan':
                ouput_df[i] = x
            else:
                ouput_df[i] = reverse_map[x]
        return ouput_df

    df_tipi = {}
    df_tipi['Extraversion']          = [df_data['TIPI extravert 1'].values,         reverse(df_data['TIPI reserved 6']).values]
    df_tipi['Agreeableness']         = [reverse(df_data['TIPI critical 2']).values, df_data['TIPI sympathetic 7'].values]
    df_tipi['Conscientiousness']     = [df_data['TIPI dependable 3'].values,        reverse(df_data['TIPI disorganized 8']).values]
    df_tipi['Emotional Stability']   = [reverse(df_data['TIPI anxious 4']).values,  df_data['TIPI calm 9'].values]
    df_tipi['Openness to Experience']= [df_data['TIPI open 5'].values,              reverse(df_data['TIPI conventional 10']).values]

    scores = collections.defaultdict(list)
    for k,v in df_tipi.items():
        item0 = []
        for x in v[0]:
            if str(x).lower() != 'nan':
                x_ = str(x).split(':')[1]
                x_ = int(str(x_).split('=')[0])
            else:
                x_ = np.nan
            item0.append(x_)
        item1 = []
        for x in v[1]:
            if str(x).lower() != 'nan':
                x_ = str(x).split(':')[1]
                x_ = int(str(x_).split('=')[0])
            else:
                x_ = np.nan
            item1.append(x_)      

        for i,x in enumerate(item0):
            y = item1[i]
            compute_score = np.nanmean(np.array([x,y]))
            scores[k].append(compute_score)                            
    scores = pd.DataFrame(scores).set_index(df['study_id'])

    tipi_scores_filename = 'baseline-survey-tipi.csv'
    tipi_scores_path = os.path.join(output_data_folder, tipi_scores_filename)
    scores.to_csv(tipi_scores_path)
    print('TIPI scores =', tipi_scores_filename)


    #--------------------------------------------------------------------------------
    #Create BREQ-2 Motivation scores

    motivation_names = {}
    count = 0
    for name in list(df.columns):
        if str(name).lower().find('motivation') != -1:
            motivation_names[count+1] = name
            count += 1
    assert(count == 19), 'there should be 19 motivation columns'

    def map_to_name(scales):
        names = []
        for scale in scales:
            names.append(motivation_names[scale])
        return names

    df_motivation = {}
    df_motivation['Amotivation']            = map_to_name([5, 9, 12, 19])
    df_motivation['External regulation']    = map_to_name([1, 6, 11, 16])
    df_motivation['Introjected regulation'] = map_to_name([2, 7, 13])
    df_motivation['Identified regulation']  = map_to_name([3, 8, 14, 17])
    df_motivation['Intrinsic regulation']   = map_to_name([4, 10, 15, 18])

    df_data = df[motivation_names.values()]
    for name in df_data.columns:
        for i, x in enumerate(df_data[name]):            
            if str(x).lower()=="nan":
                value = x
            else:
                value = int(str(x).split(':')[0])
            df_data.loc[i][name] = value

    scores = {}
    for k,v in df_motivation.items():
        scores[k] = df_data[v].mean(axis=1)    
    scores = pd.DataFrame(scores).set_index(df['study_id'])

    motivation_scores_filename = 'baseline-survey-motivation.csv'
    motivation_scores_path = os.path.join(output_data_folder, motivation_scores_filename)
    scores.to_csv(motivation_scores_path)
    print('Motivation scores =', motivation_scores_filename)    


def main(argv):

    #For example, run the following command:
    #python baseline_utils.py -d "HeartSteps_DataDictionary_2021-01-22.csv" -f "HeartSteps-BaselineSurveyData_DATA_2022-03-30_0958.csv" -o "" -p ""

    instructions = "baseline_utils.py -d <data_dict> -f <data> -o <out_data_folder> -p <out_data_dict_folder>"
    try:
        opts, args = getopt.getopt(argv,"d:f:o:p:",["data_dict=","data=","out_data_folder=","out_data_dict_folder="])
    except getopt.GetoptError:
        print('please enter the following command:', instructions)
        sys.exit(2)

    data_dictionary_filename = ''
    data_filename = ''
    for opt, arg in opts:
        if opt in ["-d", "--data_dict"]:
            data_dictionary_filename = arg
        elif opt in ["-f", "--data"]:
            data_filename = arg
        elif opt in ["-o", "--out_data_folder"]:
            output_data_folder = arg
        elif opt in ["-p", "--out_data_dict_folder"]:
            output_data_dictionary_folder = arg

    print('found output_data_dictionary_folder =', output_data_dictionary_folder)

    if data_dictionary_filename == '' or data_filename == '':
        print('please enter the following command:', instructions)
        sys.exit()

    if output_data_folder != '' and not os.path.exists(output_data_folder):
        print(output_data_folder, 'folder for data does not exist!')
        print('please enter the following command:', instructions)
        sys.exit()

    if output_data_dictionary_folder != '' and not os.path.exists(output_data_dictionary_folder):
        print(output_data_dictionary_folder, 'folder for data dictionary does not exist!')
        print('please enter the following command:', instructions)
        sys.exit()
    
    process_baseline_survey(data_dictionary_filename, data_filename, output_data_folder, output_data_dictionary_folder)

if __name__ == '__main__':    
     main(sys.argv[1:])



    


