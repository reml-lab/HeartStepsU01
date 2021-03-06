import numpy as np
import pandas as pd
import os.path
from os import path
import collections
import timeit
import pystan
import pickle
import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns
from textwrap import wrap

fig_size = (7,5)
build_time = collections.defaultdict(list)
def save_build_time(title, start_time, b_load_existing):
    duration = (int)(timeit.default_timer() - start_time)    
    if b_load_existing:
        title += ' loaded'
        print('loaded duration =', duration, 'seconds')
    else:
        title += ' compiled'
        print('compiled duration =', duration, 'seconds')
    build_time[title].append(duration)

def build_df(filename):
    df = pd.read_csv(filename).dropna()
    df['Subject ID'] = df['Subject ID'].astype(str)
    df = df.set_index(['Subject ID', 'Date'])
    return df
    
def set_name(name):
    return str(name).lower().replace(' ', '_')
    
def load_model(data_dir, model_name, model_code, b_load_existing):    
    pickle_name = model_name + '.pkl'
    pickle_name = os.path.join(data_dir, 'models/', pickle_name)                     
    b_exist = path.exists(pickle_name)
    if not b_exist:
        print(pickle_name + ' file does not exist')
        b_load_existing = False            
    if b_load_existing == False:
        print('compiling Stan model and saving to %s...' % pickle_name)
        stan_model = pystan.StanModel(model_code=model_code)
        with open(pickle_name, 'wb') as f:
            pickle.dump(stan_model, f)
    else:
        print('loading %s...' % pickle_name)
        stan_model = pickle.load(open(pickle_name, 'rb'))
    return stan_model

def get_all_participants(df):
    df = df.reset_index()
    return list(set(df['Subject ID']))

def get_df_summary(fit):
    summary_dict = fit.summary()
    df_summary = pd.DataFrame(summary_dict['summary'], columns=summary_dict['summary_colnames'], 
                  index=summary_dict['summary_rownames'])
    return df_summary

def plot_data_regression_lines(fit, title, data_x, x_name, data_y, y_name, x_lim=None, y_lim=None, b_show=True): 
    #Plot data
    plt.figure(figsize=fig_size)
    plt.scatter(data_x, data_y, s=10, alpha=.5, marker='o', label='data')    
    #Plot regression lines
    x_min = data_x.min()
    x_max = data_x.max()
    y_min = data_y.min()
    y_max = data_y.max()
    xs = np.linspace(x_min, x_max, 100)
    df_summary = get_df_summary(fit)
    alpha_mean = df_summary['mean']['alpha']
    beta_mean  = df_summary['mean']['beta']
    alpha = fit['alpha']
    beta  = fit['beta']
    sigma = fit['sigma']
    np.random.shuffle(alpha)
    np.random.shuffle(beta)
    n_samples = min(1000, len(alpha))
    for i in range(n_samples):
        plt.plot(xs, alpha[i] + beta[i] * xs, color='blue', alpha=0.005)
    plt.plot(xs, alpha_mean + beta_mean * xs, color='blue', lw=2, label='fitted')
    plt.ylabel(y_name)
    plt.xlabel(x_name)
    if x_lim != None:
        plt.ylim(y_lim)
    if x_lim != None:
        plt.xlim(x_lim)
    plot_title = "\n".join(wrap(title, 80))
    plot_title += ':\ndata and ' + str(n_samples) + ' fitted regression lines'
    plt.title(plot_title)
    plt.gcf().tight_layout()
    plt.legend(loc=4)
    if b_show:
        plt.show()
    else:
        plt.savefig(title + '_regression.png')
    plt.close('all')

def plot_trace_and_posteriors(title, fit, parameter_name, b_show=True):
    #Plot trace
    parameter_values = fit[parameter_name]
    mean = np.mean(parameter_values)
    median = np.median(parameter_values)
    ci_lower = np.percentile(parameter_values, 2.5)
    ci_upper = np.percentile(parameter_values, 97.5)
    plt.figure(figsize=fig_size)
    plt.subplot(211)
    plt.plot(parameter_values)
    plt.xlabel('samples')
    plt.ylabel(parameter_name)
    plt.axhline(mean, color='blue', lw=2)
    plt.axhline(median, color='skyblue', lw=2, ls='--')
    plt.axhline(ci_lower, ls=':', color='darkgray')
    plt.axhline(ci_upper, ls=':', color='darkgray')
    plot_title = "\n".join(wrap(title, 80))
    plot_title += ':\ntrace and posterior distribution for {}'.format(parameter_name)
    plt.title(plot_title)
    #Plot posterior mean and 95% confidence intervals
    plt.subplot(212)
    plt.hist(parameter_values, bins=50, density=True)
    sns.kdeplot(parameter_values, shade=True)
    plt.xlabel(parameter_name)
    plt.ylabel('density')
    plt.axvline(mean, color='blue', lw=2, label='mean')
    plt.axvline(median, color='skyblue', lw=2, ls='--',label='median')
    plt.axvline(ci_lower, ls=':', color='darkgray', label='95% ci')
    plt.axvline(ci_upper, ls=':', color='darkgray')
    plt.gcf().tight_layout()
    plt.legend(loc=4)
    if b_show:
        plt.show()
    else:
        plt.savefig(title + '_trace.png')
    plt.close('all')

def plot_time_series(title, df, y_name, time_name, b_show):
    plt.figure(figsize=(fig_size[0],2))
    df_plot = df.reset_index().set_index(time_name)
    df_plot[y_name].plot()
    plt.ylabel(y_name)
    plt.xlabel('')
    plt.grid(True)
    plot_title = "\n".join(wrap(title, 80)) + ': data'
    plt.title(plot_title)
    plt.gcf().tight_layout()
    if b_show:
        plt.show()
    else:
        plt.savefig(title + '_time_series.png')
    plt.close('all')
    
def fit_simple_regression_model(data_dir, df_data, y_name, x_names, n_iters=2000, warmup=1000, chains=4,
                                max_treedepth=10, x_lim=None, y_lim=None, b_load_existing=False, b_show=True):    

    model_type = 'regression'
    model_code = """
    data {
        int<lower=0> N;
        vector[N] x;
        vector[N] y;
    }
    parameters {
        real alpha;
        real beta;
        real<lower=0> sigma;
    }
    model {
        y ~ normal(alpha + beta * x, sigma);
    }
    """

    fits = []
    for x_name in x_names:
        #Compile or load model
        start_time_simple_regression = timeit.default_timer()
        model_name = model_type + '_' + set_name(y_name) + '_' + set_name(x_name)
        stan_model = load_model(data_dir, model_name, model_code, b_load_existing)

        #Fit model
        print('start fitting...\n')
        data_x = df_data[x_name].values
        data_y = df_data[y_name].values
        data = {'N': len(data_x), 'x': data_x, 'y': data_y}        
        fit = stan_model.sampling(data=data, iter=n_iters, chains=chains, warmup=warmup, thin=1, seed=0,
                                  control=dict(max_treedepth=max_treedepth))
        fits.append(fit)

        #Display summary
        title = y_name + ' vs ' + x_name + ' (' + model_type + ' model)'
        print('summary for %s =\n%s' % (title, get_df_summary(fit)))        
        save_build_time(title, start_time_simple_regression, b_load_existing)

        #Plot
        plot_data_regression_lines(fit, title, data_x, x_name, data_y, y_name, x_lim, y_lim, b_show)
        plot_trace_and_posteriors(title, fit, 'alpha', b_show)
        plot_trace_and_posteriors(title, fit, 'beta',  b_show)
        plot_trace_and_posteriors(title, fit, 'sigma', b_show)
        print('\n')
    return fits

def fit_regression_model(data_dir, df_data, y_name, x_names, n_iters=2000, warmup=1000, chains=4,
                         max_treedepth=10, b_load_existing=False, b_show=True):    

    model_type = 'regression'
    model_code = """
    data {
        int<lower=0> N;
        int<lower=0> K;
        matrix[N,K] X;
        vector[N] y;
    }
    parameters {
        real alpha;
        vector[K] beta;
        real<lower=0> sigma;
    }
    model {
        y ~ normal(X * beta + alpha, sigma);
    }
    """

    #Compile or load model
    start_time_regression = timeit.default_timer()
    model_name = model_type + '_' + set_name(y_name)
    for x_name in x_names:
        model_name += '_' + set_name(x_name)
    stan_model = load_model(data_dir, model_name, model_code, b_load_existing)

    #Fit model
    print('start fitting...\n')
    data_X = df_data[x_names].values
    data_y = df_data[y_name].values
    data = {'N': data_X.shape[0], 'K': data_X.shape[1], 'X': data_X, 'y': data_y}        
    fit = stan_model.sampling(data=data, iter=n_iters, chains=chains, warmup=warmup, thin=1, seed=0,
                              control=dict(max_treedepth=max_treedepth))

    #Display summary
    title = y_name + ' vs ' + str(x_names) + ' (' + model_type + ' model)'
    print('summary for %s =\n%s' % (title, get_df_summary(fit)))        
    save_build_time(title, start_time_regression, b_load_existing)

    #Plot
    plot_trace_and_posteriors(title, fit, 'alpha', b_show)
    for k in range(1, data_X.shape[1]+1):
        beta_name = 'beta[' + str(k) + ']'
        plot_trace_and_posteriors(title, fit, beta_name, b_show)
    plot_trace_and_posteriors(title, fit, 'sigma', b_show)
    print('\n')
    return fit

def fit_autoregressive_model(data_dir, df_data, participants, y_name, time_name,
                             n_iters=2000, warmup=1000, chains=4, max_treedepth=10,
                             degree_p=1, b_load_existing=True, b_show=True):
    
    model_type = 'autoregressive'
    model_code = """
    data {
        int<lower=0> P;
        int<lower=0> N;
        real y[N];
    }
    parameters {
        real alpha;
        real beta[P];
        real<lower=0> sigma;
    }
    model {
        for (n in (P+1):N) {
            real mu = alpha;
            for (p in 1:P)
                mu += beta[p] * y[n-p];
            y[n] ~ normal(mu, sigma);
        }
    }
    """        

    fits = []
    all_participants = get_all_participants(df_data)
    group = df_data.groupby(by=['Subject ID'])
    for participant_name in participants:
        if participant_name in all_participants:            
            df_individual = group.get_group(participant_name)

            #Compile or load model
            start_time_autoregressive = timeit.default_timer()
            model_name = model_type + str(degree_p) + '_' + participant_name + '_' + set_name(y_name)
            stan_model = load_model(data_dir, model_name, model_code, b_load_existing)

            #Fit model
            print('start fitting...\n')
            data_y = df_individual[y_name].values
            data = {'P': degree_p, 'N': len(data_y), 'y': data_y}
            fit = stan_model.sampling(data=data, iter=n_iters, chains=chains, warmup=warmup, thin=1, seed=0,
                                      control=dict(max_treedepth=max_treedepth))
            fits.append(fit)

            #Display summary
            title = participant_name + ' ' + y_name + ' (' + model_type + ' model)'
            print('summary for participant %s =\n%s' % (title, get_df_summary(fit)))  
            save_build_time(title, start_time_autoregressive, b_load_existing)

            #Plot
            plot_time_series(title, df_individual, y_name, time_name, b_show)            
            plot_trace_and_posteriors(title, fit, 'alpha', b_show)
            for p in range(1, degree_p+1):
                beta_name = 'beta[' + str(p) + ']'
                plot_trace_and_posteriors(title, fit, beta_name, b_show)
            plot_trace_and_posteriors(title, fit, 'sigma', b_show)
            print('\n')
        else:
            print('cannot find participant', participant_name)
    return fits

if __name__ == '__main__': 
    data_dir = "../../U01Data/"             #Replace with desired data_dir
    filename1 = 'df_mood_fitbit_daily.csv'  #Replace with desired csv file
    filename2 = 'df_imputed_105_10Min.csv'  #Replace with desired csv file      
    chosen_df1 = build_df(filename1)
    chosen_df2 = build_df(filename2)
    print('chosen_df1.shape =', chosen_df1.shape)
    print('chosen_df2.shape =', chosen_df2.shape)
    print()
    b_load_existing = True
    b_show = False
    if b_load_existing:
        detail = 'loaded'
    else:
        detail = 'compiled'
    n_repeats = 1 # 5
    
    for repeat in range(n_repeats):
        
        #Analysis with Daily Metrics Data
        participants = ['102', '105']
        y_name = 'Fitbit Step Count'
        x_names = ['Committed', 'Busy', 'Rested']    
        fit_simple_regression_model(data_dir, chosen_df1, y_name, x_names, y_lim=(-5000, 35000), x_lim=(0.5, 5.5),
                                    b_load_existing=b_load_existing, b_show=b_show)
        fit_regression_model(data_dir, chosen_df1, y_name, x_names, b_load_existing=b_load_existing, b_show=b_show)
        fit_autoregressive_model(data_dir, chosen_df1, participants, y_name=y_name, time_name='Date',
                                 degree_p=2, b_load_existing=b_load_existing, b_show=b_show)
        print('build_time pystan %s (repeat=%d) = %s\n\n\n' % (detail, repeat, dict(build_time)))
        pd.DataFrame.from_dict(data=build_time, orient='index').to_csv('build_time_pystan_' + detail + '.csv', header=False)
        
        
        #Analysis with Fitbit Data Per Minute
        participants = ['105']
        y_name = 'steps'
        x_names = ['Committed', 'Busy', 'Rested']
        fit_simple_regression_model(data_dir, chosen_df2, y_name, x_names, n_iters=500, warmup=200, chains=4,
                                    b_load_existing=b_load_existing, b_show=b_show)
        fit_regression_model(data_dir, chosen_df2, y_name, x_names, n_iters=1000, warmup=300, chains=1, max_treedepth=12,
                             b_load_existing=b_load_existing, b_show=b_show)
        fit_autoregressive_model(data_dir, chosen_df2, participants, y_name=y_name, time_name='Date',
                                 degree_p=2, b_load_existing=b_load_existing, b_show=b_show)        
        print('build_time pystan %s (repeat=%d) = %s\n\n\n' % (detail, repeat, dict(build_time)))
        pd.DataFrame.from_dict(data=build_time, orient='index').to_csv('build_time_pystan_' + detail + '.csv', header=False)
        
    print('finished!')
