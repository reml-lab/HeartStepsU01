import pandas as pd
import seaborn as sn
import matplotlib.pyplot as plt
from matplotlib.pyplot import cm

import statsmodels.api as sm
import statsmodels.formula.api as smf

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score

from . import data_utils


def process_morning_survey(df):
    #Get Mood categories and create new columns
    df['Mood'] = pd.Categorical(df['Mood'])
    df['Mood Code'] = df['Mood'].cat.codes
    categories = dict(enumerate(df['Mood'].cat.categories))

    for key, value in categories.items():
        df[value] = df['Mood Code'].apply(lambda x: True if x == key else False)

    column_list = ['Busy', 'Committed', 'Rested']    
    for key, value in categories.items():
        column_list.append(value)
    df_selected = df[column_list]

    return df_selected

def process_daily_metrics(df):
    return  df[['Fitbit Step Count', 'Fitbit Minutes Worn']]

def get_correlations(df):
    df = df.replace({True: 1, False: 0})    
    correlations = df.corr()
    plt.figure(figsize=(9,8))
    sn.heatmap(correlations, cmap=cm.seismic, annot=True, vmin=-1, vmax=1)

def perform_linear_regression(df):
    df = df.dropna()
    df = df.replace({True: 1, False: 0})
    df = df.reset_index()

    y_names = {'Fitbit Step Count': 'step_count',
               'Fitbit Minutes Worn': 'minutes_worn'}

    df = df.rename(columns=y_names)
    df = df.rename(columns={'Subject ID': 'subject_id' })
    
    equation  = " ~ Busy + Committed + Rested + Energetic"
    equation += " + Fatigued + Happy + Relaxed + Sad + Stressed + Tense"    

    for y_display, y_name in y_names.items():        
        model = y_name + equation

        drop_columns = ['subject_id', 'Date'] + list(y_names.values())        
        X = df.drop(columns=drop_columns, axis=1).values
        y = df[y_name].values
        mod  = smf.ols(model, data=df)
        res0 = mod.fit()
        print('%s =\n%s\n\n\n' % (y_display, res0.summary()))

        ind = sm.cov_struct.Exchangeable()
        mod = smf.gee(model, "subject_id", data=df, cov_struct=ind)    
        res1 = mod.fit()
        print('%s =\n%s\n\n\n' % (y_display, res1.summary()))

        mod = smf.mixedlm(model, df, groups="subject_id")    
        res2 = mod.fit()
        print('%s =\n%s\n\n\n' % (y_display, res2.summary()))

        df_coef = res0.params.to_frame().rename(columns={0: 'coef'})
        ax = df_coef.plot.barh(figsize=(14, 7))
        ax.axvline(0, color='black', lw=1)
        plt.title(y_display + ' using OLS')
        
        df_coef = res1.params.to_frame().rename(columns={0: 'coef'})
        ax = df_coef.plot.barh(figsize=(14, 7))
        ax.axvline(0, color='black', lw=1)
        plt.title(y_display + ' using GEE Regression')

        df_coef = res2.params.to_frame().rename(columns={0: 'coef'})
        ax = df_coef.plot.barh(figsize=(14, 7))
        ax.axvline(0, color='black', lw=1)
        plt.title(y_display + ' using Mixed Linear Model Regression')

def perform_classification(df):
    df = df.dropna()
    df = df.replace({True: 1, False: 0})
    df = df.reset_index()
    df = df.drop(columns=['Fitbit Minutes Worn', 'Subject ID', 'Date'])      

    #Turn Fitbit Step Count per day into a binary variable steps = 0 and steps > 0
    column_name = 'Fitbit Step Count'
    df[column_name] = df[column_name].apply(lambda x: 1 if x > 0 else 0)
    
    X = df.drop(columns=column_name).values
    y = df[column_name].values

    # Split the data and targets into training/testing sets
    split_percent = 0.8
    split = int(len(X) * split_percent)    
    X_train = X[:split]
    X_test  = X[split:]
    y_train = y[:split]
    y_test  = y[split:]

    print('Classification for ' + column_name)
    print('\ntrain split   = {}%'.format(int(split_percent*100)))
    print('X_train.shape =', X_train.shape)
    print('y_train.shape =', y_train.shape)
    print('X_test.shape  =', X_test.shape)
    print('y_test.shape  =', y_test.shape)    

    model = LogisticRegression(solver='lbfgs', random_state=0)
    model.fit(X_train, y_train)
    y_predict = model.predict(X_test)

    print('\nmodel =', model)
    print('\ntrain accuracy =', accuracy_score(y_train, model.predict(X_train)))
    print('test  accuracy =', accuracy_score(y_test,  model.predict(X_test)))

