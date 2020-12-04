import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn
import os
import zipfile
from IPython.display import display, Markdown, Latex
from ipywidgets import interact, interactive, fixed, interact_manual
import ipywidgets as widgets
from . import data_utils


def plot_summary_histograms(df, dd, cols=3, fields=[]):  
    num_fields = len(dd["categorical_fields"])+len(dd["numerical_fields"])
    rows = int(np.ceil(num_fields/3))
    fig, axes = plt.subplots(rows, cols, figsize=(4*3,rows*3))
    i=0
    for field in list(df.keys()):
        if(field in fields or len(fields)==0):
            if field in dd["categorical_fields"]:
                this_ax = axes[i//cols,i%cols]
                df[field].value_counts().plot(kind="bar",ax=this_ax)
                this_ax.grid(axis='y')
                this_ax.set_title(field)
                i=i+1
            if field in dd["numerical_fields"]: 
                this_ax = axes[i//cols,i%cols]
                df[field].hist(figure=fig,ax=this_ax)
                this_ax.grid(True)
                this_ax.set_title(field)
                i=i+1
    plt.tight_layout()
    plt.show()

def plot_indifivual_time_series(df,variable,subject_id):
  this_df = df.xs(subject_id, level=0, axis=0, drop_level=True)
  this_df[variable].plot(kind='bar', grid=True, figsize=(12,4) )
  plt.title("Subject %s: %s"%(subject_id,variable))
  plt.show()

def show_individual_time_series_visualizer(df):
  sids=data_utils.get_subject_ids(df)
  vars=get_variables(df)
  interact(plot_indifivual_time_series, df=fixed(df), subject_id=sids,variable = vars);