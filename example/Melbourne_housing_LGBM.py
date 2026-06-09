# -*- coding: utf-8 -*-
"""
Created on Fri Sep 24 10:08:24 2021

@author: Jean
"""

# Imports
# Ignore Warnings 
import warnings
warnings.filterwarnings('ignore')

# Basic Imports 
import numpy as np
import pandas as pd
import time

# Plotting 
import matplotlib.pyplot as plt

# Preprocessing
from sklearn.model_selection import train_test_split, KFold, cross_val_score

# Metrics 
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

# ML Models
import lightgbm as lgb
from lightgbm import LGBMRegressor 
import xgboost as xg 
from sklearn.ensemble import RandomForestRegressor
from sklearn import svm

# Model Tuning 
from bayes_opt import BayesianOptimization
from hyperopt import fmin, tpe, hp, Trials
from hyperopt.fmin import generate_trials_to_calculate

# Feature Importance 
import shap
    
# Reading a CSV File
# 9015
df_NN = pd.read_csv("D:/temp/data/Melbourne_housing/Melbourne_housing_pre.csv",  encoding="utf-8")

X=df_NN[['Year','YearBuilt','Distance','Lattitude','Longtitude','Propertycount',
          'Landsize','BuildingArea', 'Rooms','Bathroom', 'Car','Type_h','Type_t','Type_u']]
y=df_NN['LogPrice']
train_X, valid_X, train_y, valid_y = train_test_split(X,y, test_size = .20, random_state=42)

train_X2 = train_X.copy()
valid_X2 = valid_X.copy()

# Data standardization
mean = train_X.mean(axis=0)
train_X -= mean
std = train_X.std(axis=0)
train_X /= std
valid_X -= mean
valid_X /= std


##% evaluateRegressor
# from sklearn.metrics import mean_squared_error, mean_absolute_error
def evaluateRegressor(true,predicted,message = "Test set"):
    MSE = mean_squared_error(true,predicted,squared = True)
    MAE = mean_absolute_error(true,predicted)
    RMSE = mean_squared_error(true,predicted,squared = False)
    LogRMSE = mean_squared_error(np.log(true),np.log(predicted),squared = False)
    R2 = r2_score(true,predicted)
    print(message)
    print("MSE:", MSE)
    print("MAE:", MAE)
    print("RMSE:", RMSE)
    print("LogRMSE:", LogRMSE)
    print("R2 :", R2)
    
##% Plot True vs predicted values. Useful for continuous y 
def PlotPrediction(true,predicted, title = "Dataset: "):
    fig = plt.figure(figsize=(20,20))
    ax1 = fig.add_subplot(111)
    ax1.set_title(title + 'True vs Predicted')
    ax1.scatter(list(range(0,len(true))),true, s=10, c='r', marker="o", label='True')
    ax1.scatter(list(range(0,len(predicted))), predicted, s=10, c='b', marker="o", label='Predicted')
    plt.legend(loc='upper right');
    plt.show()    
    
##% Initial Models
RFReg = RandomForestRegressor(random_state = 0).fit(train_X, train_y)
SVM = svm.SVR().fit(train_X, train_y) 
XGReg = xg.XGBRegressor(objective ='reg:squarederror', seed = 0,verbosity=0).fit(train_X,train_y) 
LGBMReg = lgb.LGBMRegressor(random_state=0).fit(train_X,train_y)

##% Model Metrics
print("Random Forest Regressor") 
predicted_train_y = RFReg.predict(train_X)
evaluateRegressor(train_y,predicted_train_y,"    Training Set")
predicted_valid_y = RFReg.predict(valid_X)
evaluateRegressor(valid_y,predicted_valid_y,"    Test Set")
print("\n")
    
print("Support Vector Machine") 
predicted_train_y = SVM.predict(train_X)
evaluateRegressor(train_y,predicted_train_y,"    Training Set")
predicted_valid_y = SVM.predict(valid_X)
evaluateRegressor(valid_y,predicted_valid_y,"    Test Set")
print("\n")


print("XGBoost Regressor") 
predicted_train_y = XGReg.predict(train_X)
evaluateRegressor(train_y,predicted_train_y,"    Training Set")
predicted_valid_y = XGReg.predict(valid_X)
evaluateRegressor(valid_y,predicted_valid_y,"    Test Set")
print("\n")

print("LightGBM Regressor") 
predicted_train_y = LGBMReg.predict(train_X)
evaluateRegressor(train_y,predicted_train_y,"    Training Set")
predicted_valid_y = LGBMReg.predict(valid_X)
evaluateRegressor(valid_y,predicted_valid_y,"    Test Set")


# --------------------------------------------------------------------------------------------------
# Auto search for better hyper parameters with hyperopt, only need to give a range
# Reference: https://www.pythonf.cn/read/6998
#            https://lightgbm.readthedocs.io/en/latest/Parameters.html
#            https://lightgbm.readthedocs.io/en/latest/Parameters-Tuning.html#deal-with-over-fitting
#            https://lightgbm.readthedocs.io/en/latest/GPU-Performance.html
# 处理过拟合

#     设置较少的直方图数目 max_bin
#     设置较小的叶节点数 num_leaves
#     使用 min_child_samples（min_data_in_leaf） 和 min_child_weight（= min_sum_hessian_in_leaf）
#     通过设置 subsample（bagging_fraction） 和 subsample_freq（= bagging_freq） 来使用 bagging
#     通过设置 colsample_bytree（feature_fraction） 来使用特征子抽样
#     使用更大的训练数据
#     使用 reg_alpha（lambda_l1） , reg_lambda（lambda_l2） 和 min_split_gain（min_gain_to_split） 来使用正则
#     尝试 max_depth 来避免生成过深的树
#     Try extra_trees
#     Try increasing path_smooth

# trials = generate_trials_to_calculate([{'max_bin':63-8,               # default CPU 255 GPU 63
#                                         'max_depth':5-3,              # default -1
#                                         'num_leaves':31-20,           # default 31
#                                         'min_child_samples':20-10,    # default 20
#                                         'subsample_freq':1-1,         # default 1
#                                         'n_estimators':6000-1000,     # default 10
#                                         'learning_rate':0.01,         # default 0.1
#                                         'subsample':0.75,             # default 1.0
#                                         'colsample_bytree':0.8,       # default 1.0
#                                         'lambda_l1':0.0,              # default 0.0
#                                         'lambda_l2':0.0,              # default 0.0
#                                         'min_child_weight':0.001,     # default 0.001
#                                         'min_split_gain':0.0,         # default 0.0
#                                         #'path_smooth':0.0            # default 0.0
#                                         }])
# 缩小参数取值范围，搜索会快很多  
space_lgbm = {
    'max_bin': hp.choice('max_bin', range(50, 501)),                  # CPU 50-501 GPU 8-128
    'max_depth': hp.choice('max_depth', range(3, 31)),    
    'num_leaves': hp.choice('num_leaves', range(10, 256)),
    'min_child_samples': hp.choice('min_child_samples', range(10, 51)), 
    'subsample_freq': hp.choice('subsample_freq', range(1, 6)),      
    'n_estimators': hp.choice('n_estimators', range(500, 6001)),
    'learning_rate': hp.uniform('learning_rate', 0.005, 0.15),    
    'subsample': hp.uniform('subsample', 0.5, 0.99),
    'colsample_bytree': hp.uniform('colsample_bytree', 0.5, 0.99),
    'reg_alpha': hp.uniform('reg_alpha', 0, 5),                       # lambda_l1
    'reg_lambda': hp.uniform('reg_lambda', 0, 3),                     # lambda_l2
    'min_child_weight': hp.uniform('min_child_weight',0.0001, 50),
    'min_split_gain': hp.uniform('min_split_gain',0.0, 1),
    #'path_smooth': hp.uniform('path_smooth',0.0, 3)
}
def f_lgbm(params):
    # Set extra_trees=True to avoid overfitting
    lgbm = LGBMRegressor(seed=0,verbose=-1, **params)                 # CPU 4.96s/trial
    # lgbm = LGBMRegressor(device='gpu', gpu_platform_id=1, gpu_device_id = 0, num_threads =3, **params)    # GPU 65.93s/trial
    #lgb_model = lgbm.fit(train_X, train_y)
    #acc = lgb_model.score(valid_X,valid_y)
    acc = cross_val_score(lgbm, train_X, train_y).mean()             # CPU
    # acc = cross_val_score(lgbm, train_X, train_y, n_jobs=6).mean()  # GPU
    return -acc
# trials = Trials()
# Set initial values, start searching from the best point of GridSearchCV(), and default values
trials = generate_trials_to_calculate([{'max_bin':255,                # default CPU 255 GPU 63
                                        'max_depth':17,                             # default -1
                                        'num_leaves':12,                            # default 31
                                        'min_child_samples':14,                     # default 20
                                        'subsample_freq':0,                         # default 1
                                        'n_estimators':2647,                        # default 10
                                        'learning_rate':0.0203187560767722,         # default 0.1
                                        'subsample':0.788703175392162,              # default 1.0
                                        'colsample_bytree':0.5203150334508861,      # default 1.0
                                        'reg_alpha': 0.988139501870491,             # default 0.0
                                        'reg_lambda':2.789779486137205,             # default 0.0
                                        'min_child_weight':21.813225361674828,      # default 0.001
                                        'min_split_gain':0.00039636685518264865,    # default 0.0
                                        #'path_smooth':0.0                          # default 0.0
                                        }])

t1 = time.time()  
# 1000trial [5:23:09, 19.39s/trial, best loss: -0.9082183160929432] CPU  
# 1000trial [1:22:39,  4.96s/trial, best loss: -0.9079837941918502] CPU 
# 1000trial [5:39:51, 20.39s/trial, best loss: -0.9068431932173453] GPU     
# 1000trial [1:02:28,  3.75s/trial, best loss: -0.9080477825539048] CPU
# 1000trial [18:55,  1.14s/trial, best loss: -0.9029308764279137] CPU
# 1000trial [1:14:40,  4.48s/trial, best loss: -0.9253639597148784] CPU
best_params = fmin(f_lgbm, space_lgbm, algo=tpe.suggest, max_evals=99, trials=trials)
t2 = time.time()
# 19390.56170320511 4960.896098852158 20392.74730038643GPU 3749.3419647216797 1136.1463103294373 4481.4692125320435
print("Time elapsed: ", t2-t1)

print('best:')
# CPU {'colsample_bytree': 0.5000455292913467, 'reg_alpha': 0.15545644376537782, 'reg_lambda': 1.4080091797633087, 'learning_rate': 0.007561841813178302, 'max_bin': 419, 'max_depth': 39, 'min_child_weight': 9.330764246889554, 'n_estimators': 4716, 'num_leaves': 12, 'subsample': 0.5887399629302962}
# CPU {'colsample_bytree': 0.5740856868933041, 'reg_alpha': 0.4978659241908678, 'reg_lambda': 2.9895546493896226, 'learning_rate': 0.01664367400440669, 'max_bin': 86, 'max_depth': 5, 'min_child_samples': 29, 'min_child_weight': 22.863111407056216, 'min_split_gain': 0.0003417086853309451, 'n_estimators': 4428, 'num_leaves': 10, 'subsample': 0.9538662288625716, 'subsample_freq': 1}
# GPU {'colsample_bytree': 0.7103345027555479, 'reg_alpha': 1.0133278908262167, 'reg_lambda': 0.42903027120676573, 'learning_rate': 0.014545969324488227, 'max_bin': 96, 'max_depth': 3, 'min_child_samples': 10, 'min_child_weight': 15.450385729945399, 'min_split_gain': 0.0016071587697570192, 'n_estimators': 4528, 'num_leaves': 8, 'subsample': 0.7242389855352034, 'subsample_freq': 4} 
# CPU {'colsample_bytree': 0.5203150334508861, 'reg_alpha': 0.988139501870491, 'reg_lambda': 2.789779486137205, 'learning_rate': 0.0203187560767722, 'max_bin': 278, 'max_depth': 17, 'min_child_samples': 14, 'min_child_weight': 21.813225361674828, 'min_split_gain': 0.00039636685518264865, 'n_estimators': 2647, 'num_leaves': 12, 'subsample': 0.788703175392162, 'subsample_freq': 0}
# CPU {'colsample_bytree': 0.5142540541056978, 'learning_rate': 0.014284678929509775, 'max_bin': 161, 'max_depth': 4, 'min_child_samples': 5, 'min_child_weight': 4.534457967283932, 'min_split_gain': 0.0006363777341674458, 'n_estimators': 2006, 'num_leaves': 93, 'reg_alpha': 0.0037820689583625278, 'reg_lambda': 2.947360470949046, 'subsample': 0.9448608935296047, 'subsample_freq': 2}
# CPU {'colsample_bytree': 0.5482469765978001, 'learning_rate': 0.02138706516193863, 'max_bin': 211, 'max_depth': 25, 'min_child_samples': 9, 'min_child_weight': 26.29858787655885, 'min_split_gain': 0.00038968894882169256, 'n_estimators': 4731, 'num_leaves': 19, 'reg_alpha': 0.8257383468656769, 'reg_lambda': 1.3981267479316741, 'subsample': 0.750429969832067, 'subsample_freq': 2}
print(best_params)

# verify
params = best_params.copy()
# restore best hyper parameters
params = {'colsample_bytree': 0.5142540541056978, 'learning_rate': 0.014284678929509775, 'max_bin': 161, 'max_depth': 4, 'min_child_samples': 5, 'min_child_weight': 4.534457967283932, 'min_split_gain': 0.0006363777341674458, 'n_estimators': 2006, 'num_leaves': 93, 'reg_alpha': 0.0037820689583625278, 'reg_lambda': 2.947360470949046, 'subsample': 0.9448608935296047, 'subsample_freq': 2}
params['max_bin'] = params['max_bin']+50
params['max_depth'] = params['max_depth']+3
params['num_leaves'] = params['num_leaves']+20
params['min_child_samples'] = params['min_child_samples']+10
params['subsample_freq'] = params['subsample_freq']+1
params['n_estimators'] = params['n_estimators']+1000
print(params)

# Original best parameters of GridSearchCV()
# Set extra_trees=True to avoid overfitting
lgbm_best = LGBMRegressor(seed=0, **params)
acc = cross_val_score(lgbm_best, train_X, train_y).mean()
# 0.9082183160929432 0.9069692181747394  0.9066523433423663GPU 0.9078336217424837 0.9075054302960665 0.9248809113205866
print(acc)

# predict
lgb_model_full_data = lgbm_best.fit(train_X, train_y)
# 0.9727223028335408 0.9749978871820015  0.9662169060275624GPU 0.9701937780242721 0.9790954758709947 0.9840188541116298
print(lgb_model_full_data.score(train_X,train_y))
# 0.9010664296217231 0.9005194608968802  0.8994218457293254GPU 0.9005790300507339 0.9031159392716986 0.8983448264278595
print(lgb_model_full_data.score(valid_X,valid_y))

# evalute model using the entire dataset from Train.csv
evaluateRegressor(train_y,lgb_model_full_data.predict(train_X),"Train set ")
evaluateRegressor(valid_y,lgb_model_full_data.predict(valid_X),"Valid set ")


def PlotPrediction2(true,predicted, title = "Dataset: "):
    df = pd.DataFrame({"Real":true,"Predicted":predicted})
    df.sort_values(by=["Real"], inplace=True)
    df = df.reset_index(drop=True)
    fig = plt.figure(figsize=(20,20))
    plt.tick_params(labelsize=20)
    ax1 = fig.add_subplot(111)
    ax1.set_title(title + 'True vs Predicted', fontsize=40)
    ax1.plot(list(range(0,len(df["Predicted"]))),df["Predicted"],'b-',label='Predicted')
    ax1.plot(list(range(0,len(df["Real"]))),df["Real"],'r-',label='True') 
    plt.xlabel("Samples in Value Order", fontsize=30)
    plt.ylabel("Log Price", fontsize=30)
    plt.legend(loc='upper left',fontsize=30 );
    plt.show()    
    
PlotPrediction2(train_y,lgb_model_full_data.predict(train_X),"Train set: ")
PlotPrediction2(valid_y,lgb_model_full_data.predict(valid_X),"Valid set: ")

##% Feature Importance 
# https://scikit-learn.org/stable/auto_examples/ensemble/plot_forest_importances.html
lgb.plot_importance(lgbm_best,figsize=(25,20))

##% Feature Importance using shap package 
# https://zhuanlan.zhihu.com/p/83412330
# https://zhuanlan.zhihu.com/p/106320452
# Should use TreeExplainer for LightGBM tree base algorithms
shap_values = shap.TreeExplainer(lgbm_best).shap_values(valid_X)
shap.summary_plot(shap_values, valid_X)
# a different importance plot of shap_values
shap.summary_plot(shap_values, valid_X, plot_type="bar")
# Feature importance for a single sample
# shap.initjs()  # notebook环境下，加载用于可视化的JS代码
# 如果不想用JS,传入matplotlib=True, 
row = 0
shap.force_plot(valid_y.mean(), shap_values[row], np.round(valid_X.iloc[row],4),matplotlib=True,text_rotation=30)
# better to plot with original feature values
shap.force_plot(valid_y.mean(), shap_values[row], valid_X2.iloc[row],matplotlib=True,text_rotation=30)
# matplotlib = True is not yet supported for force plots with multiple samples!
shap.force_plot(valid_y.mean(), shap_values[0:3], X[0:3],matplotlib=True)
# create a SHAP dependence plot to show the effect of a single feature across the whole dataset
shap.dependence_plot("BuildingArea", shap_values, valid_X)

# print one trail to see the result structure
for t in trials:
    print(t)
    break

# hyperparameter is not relevant to a particular trial.
def unpack(x):
    if x:
        return x[0]
    return np.nan

# We'll first turn each trial into a series and then stack those series together as a dataframe.
trials_df = pd.DataFrame([pd.Series(t["misc"]["vals"]).apply(unpack) for t in trials])
# Then we'll add other relevant bits of information to the correct rows and perform a couple of
# mappings for convenience
trials_df["loss"] = [t["result"]["loss"] for t in trials]
trials_df["trial_number"] = trials_df.index
trials_df.to_csv("D:/temp/data/LightGBM_1000_trials2.csv")

def PlotTrial(trials,loss):
    fig = plt.figure(figsize=(20,20))
    plt.tick_params(labelsize=20)
    ax1 = fig.add_subplot(111)
    ax1.set_title('Loss per Trial', fontsize=40)
    ax1.plot(trials,loss,'b.',label='loss')
    # ax1.plot(list(range(0,len(df["Real"]))),df["Real"],'r-',label='True') 
    plt.xlabel("Trial", fontsize=30)
    plt.ylabel("Loss", fontsize=30)
    plt.legend(loc='upper left',fontsize=30 );
    plt.show()  
    
PlotTrial(trials_df['trial_number'], trials_df['loss'])    

trials_df["max_depth"].value_counts()
# draw contour plot with plotly in jupyter notebook then.



# --------------------------------------------------------------------------------------------------------------

# Bayesian Optimization in another way
##% parameter tuning for lightgbm 
# store the catagorical features names as a list      
# cat_features = X_train_clean_encoded.select_dtypes(['object']).columns.to_list()
cat_features = None

# Create the LightGBM data containers
# Make sure that cat_features are used
train_data=lgb.Dataset(train_X,label=train_y, categorical_feature = cat_features,free_raw_data=False)
valid_data=lgb.Dataset(valid_X,label=valid_y, categorical_feature = cat_features,free_raw_data=False)

# Native API
# https://medium.com/analytics-vidhya/hyperparameters-optimization-for-lightgbm-catboost-and-xgboost-regressors-using-bayesian-6e7c495947a9
# from lightgbm import LGBMRegressor 
# from bayes_opt import BayesianOptimization
def search_best_param(X,y,cat_features, n_iter = 10):
    
    trainXY = lgb.Dataset(data=X, label=y,categorical_feature = cat_features,free_raw_data=False)
    # define the lightGBM cross validation
    def lightGBM_CV(max_depth, num_leaves, n_estimators, learning_rate, subsample, colsample_bytree, 
                lambda_l1, lambda_l2, min_child_weight):
    
        params = {'boosting_type': 'gbdt', 'objective': 'regression', 'metric':'rmse', 'verbose': -1,
                  'early_stopping_round':100}
        
        params['max_depth'] = int(round(max_depth))
        params["num_leaves"] = int(round(num_leaves))
        params["n_estimators"] = int(round(n_estimators))
        params['learning_rate'] = learning_rate
        params['subsample'] = subsample
        params['colsample_bytree'] = colsample_bytree
        params['lambda_l1'] = max(lambda_l1, 0)
        params['lambda_l2'] = max(lambda_l2, 0)
        params['min_child_weight'] = min_child_weight
        #params['device'] = 'cpu'

    
        score = lgb.cv(params, trainXY, nfold=5, seed=1, stratified=False, verbose_eval =False, metrics=['rmse'])

        return -np.min(score['rmse-mean']) # return negative rmse to minimize rmse 

    # use bayesian optimization to search for the best hyper-parameter combination
    lightGBM_Bo = BayesianOptimization(lightGBM_CV, 
                                       {
                                          'max_depth': (3, 50),              # 5
                                          'num_leaves': (20, 100),
                                          'n_estimators': (50, 7000),        # 1000
                                          'learning_rate': (0.005, 0.15),    # 0.01, 0.3
                                          'subsample': (0.5, 0.99),
                                          'colsample_bytree' :(0.5, 0.99),
                                          'lambda_l1': (0, 5),
                                          'lambda_l2': (0, 3),
                                          'min_child_weight': (0.0001, 50)   # 2
                                      },
                                       random_state = 1,
                                       verbose = 0
                                      )

    np.random.seed(1)
    
    lightGBM_Bo.maximize(init_points=5, n_iter= n_iter) 
    
    params_set = lightGBM_Bo.max['params']
    
    # get the params of the maximum target     
    max_target = -np.inf
    for i in lightGBM_Bo.res: # loop thru all the residuals 
        if i['target'] > max_target:
            params_set = i['params']
            max_target = i['target']
    
    params_set.update({'verbose': -1})
    params_set.update({'metric': 'rmse'})
    params_set.update({'boosting_type': 'gbdt'})
    params_set.update({'objective': 'regression'})
    
    params_set['max_depth'] = int(round(params_set['max_depth']))
    params_set['num_leaves'] = int(round(params_set['num_leaves']))
    params_set['n_estimators'] = int(round(params_set['n_estimators']))
    params_set['seed'] = 1 #set seed
    
    return params_set

t1 = time.time()
best_params = search_best_param(train_X,train_y,cat_features,1000)
t2 = time.time()
# 6275.472637176514
print("Time elapsed: ", t2-t1)

# Print best_params
# colsample_bytree  :  0.6402645216775418
# lambda_l1  :  0.7508289545995278
# lambda_l2  :  2.3604391662736552
# learning_rate  :  0.016440493543250237
# max_depth  :  28
# min_child_weight  :  12.952397542773076
# n_estimators  :  6311
# num_leaves  :  26
# subsample  :  0.9665323309115375
# verbose  :  -1
# metric  :  rmse
# boosting_type  :  gbdt
# objective  :  regression
# seed  :  1
for key, value in best_params.items():
    print(key, ' : ', value)

# Train lgbm_best using the best params found from Bayesian Optimization
t1 = time.time()
lgbm_best = lgb.train(best_params,
                 train_data,
                 num_boost_round = 2500,
                 valid_sets = valid_data,
                 early_stopping_rounds = 200,
                 verbose_eval = 100
                 )
t2 = time.time()
# 2.3467249870300293
print("Time elapsed: ", t2-t1)

print("LightGBM Regressor Tuned") 
predicted_train_y = lgbm_best.predict(train_X)
evaluateRegressor(train_y,predicted_train_y,"    Training Set")
PlotPrediction(train_y,predicted_train_y,"Training Set: ")

predicted_valid_y = lgbm_best.predict(valid_X)
evaluateRegressor(valid_y,predicted_valid_y,"    Test Set")
PlotPrediction(valid_y,predicted_valid_y,"Test Set: ")

##% Feature Importance 
# https://scikit-learn.org/stable/auto_examples/ensemble/plot_forest_importances.html
lgb.plot_importance(lgbm_best,figsize=(25,20))

##% Feature Importance using shap package 
# http://sofasofa.io/tutorials/shap_xgboost/
# import shap
lgbm_best.params['objective'] = 'regression'
shap_values = shap.TreeExplainer(lgbm_best).shap_values(valid_X)
shap.summary_plot(shap_values, valid_X)
# a different importance plot of shap_values
shap.summary_plot(shap_values, valid_X, plot_type="bar")

# Cross Validation with LightGBM

def K_Fold_LightGBM(X_train, y_train , cat_features, num_folds = 3):
    num = 0
    models = []
    folds = KFold(n_splits=num_folds, shuffle=True, random_state=0)

        # 5 times 
    for n_fold, (train_idx, valid_idx) in enumerate (folds.split(X_train, y_train)):
        print(f"     model{num}")
        train_X, train_y = X_train.iloc[train_idx], y_train.iloc[train_idx]
        valid_X, valid_y = X_train.iloc[valid_idx], y_train.iloc[valid_idx]
        
        train_data=lgb.Dataset(train_X,label=train_y, categorical_feature = cat_features,free_raw_data=False)
        valid_data=lgb.Dataset(valid_X,label=valid_y, categorical_feature = cat_features,free_raw_data=False)
        
        params_set = search_best_param(train_X,train_y,cat_features)
        
        CV_LGBM = lgb.train(params_set,
                            train_data,
                            num_boost_round = 2500,
                            valid_sets = valid_data,
                            early_stopping_rounds = 200,
                            verbose_eval = 100
                           )
        
        # increase early_stopping_rounds can lead to overfitting 
        models.append(CV_LGBM)
        
        print("Train set logRMSE:", mean_squared_error(np.log(train_y),np.log(models[num].predict(train_X)),squared = False))
        print(" Test set logRMSE:", mean_squared_error(np.log(valid_y),np.log(models[num].predict(valid_X)),squared = False))
        print("\n")
        num = num + 1
        
    return models

t1 = time.time()
lgbm_models = K_Fold_LightGBM(train_X,train_y,cat_features,5)
t2 = time.time()
# 170.7221701145172
print("Time elapsed: ", t2-t1)

# Predict y_prds using models from cross validation 
def predict_cv(models_cv,X):
    y_preds = np.zeros(shape = X.shape[0])
    for model in models_cv:
        y_preds += model.predict(X)
        
    return y_preds/len(models_cv)

# evalute model using the entire dataset from Train.csv
evaluateRegressor(train_y,predict_cv(lgbm_models,train_X),"Train set ")
PlotPrediction(train_y,predict_cv(lgbm_models,train_X),"Train set: ")

# predictLGBM = lgbm_best.predict(valid_X)
# submissionLGBM = pd.DataFrame({'Id':test_Id,'LogPrice':predictLGBM})
# display(submissionLGBM.head())

# predictLGBM_CV = predict_cv(lgbm_models,valid_X)
# submissionLGBM_CV = pd.DataFrame({'Id':test_Id,'LogPrice':predictLGBM_CV})
# display(submissionLGBM_CV.head())

# ##% Submit Predictions 
# submissionLGBM.to_csv('submissionLGBM4.csv',index=False)
# submissionLGBM_CV.to_csv('submissionLGBM_CV4.csv',index=False)


# ---drop outliers in train set and train again
train_X2 = train_X.copy()
train_y2 = train_y.copy()

predictions = lgbm_best.predict(train_X)
df = pd.DataFrame({"real":train_y,"predicts":predictions})
indexs = (df["predicts"]<=df["real"]+np.log(1.2)) & (df["predicts"]>=df["real"]+np.log(0.8))
indexs.value_counts()
train_X = train_X[indexs==True]
train_y = train_y[indexs==True]
outliers_X = train_X2[indexs!=True]
outliers_y = train_y2[indexs!=True]


