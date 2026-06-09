# -*- coding: utf-8 -*-
"""
Created on Wed Sep  1 16:23:15 2021

@author: Jean
"""

'''
This data was scraped from publicly available results posted every week from Domain.com.au.
Update 22/05/2018.

Some Key Details of the dataset

Suburb: Suburb

Address: Address

Rooms: Number of rooms

Price: Price in Australian dollars

Method:
S - property sold;
SP - property sold prior;
PI - property passed in;
PN - sold prior not disclosed;
SN - sold not disclosed;
NB - no bid;
VB - vendor bid;
W - withdrawn prior to auction;
SA - sold after auction;
SS - sold after auction price not disclosed.
N/A - price or highest bid not available.

Type:
br - bedroom(s);
h - house,cottage,villa, semi,terrace;
u - unit, duplex;
t - townhouse;
dev site - development site;
o res - other residential.

SellerG: Real Estate Agent

Date: Date sold

Distance: Distance from CBD in Kilometres

Regionname: General Region (West, North West, North, North east …etc)

Propertycount: Number of properties that exist in the suburb.

Bedroom2 : Scraped # of Bedrooms (from different source)

Bathroom: Number of Bathrooms

Car: Number of carspots

Landsize: Land Size in Metres

BuildingArea: Building Size in Metres

YearBuilt: Year the house was built

CouncilArea: Governing council for the area

Lattitude: Self explanitory

Longtitude: Self explanitory
'''

# Data Pre-processing
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import  r2_score

# Reading a CSV File
# 34857
df = pd.read_csv("D:/temp/data/Melbourne_housing/Melbourne_housing_FULL.csv",  encoding="utf-8")
# Displays dimension of the dataset i.e no. of rows and columns
df.shape
# 34856
df = df.drop_duplicates()
# 8887, too less data, so we must use impution to deal with null values
df2 = df.dropna()

# Displaying first five records of datset
df.head()
# Displays dimension of the dataset i.e no. of rows and columns
df.shape
df.info()
# Describe the dataset
df.describe()
df.describe().T

# Slicing for first 20 rows for the column named 'Method'.
df[0:20]['Method']
# Displaying first 10 records of attributes 'Distane' and 'Price'
df.loc[0:10,['Distance','Price']]
# Count no. of unique values in the column 'Method'
df['Method'].value_counts()

#separate the numeric columns from the categorical columns
# select numerical columns
data_numeric = df.select_dtypes(include=[np.number])
numeric_cols = data_numeric.columns.values
# select non-numeric columns
data_non_numeric = df.select_dtypes(exclude=[np.number])
non_numeric_cols = data_non_numeric.columns.values
numeric_cols
non_numeric_cols
# Printing contents of attribute 'Price'
df['Price']

# After carefully evaluating data, it can be noticed that variables "Rooms" and "Bedroom2" 
# are pretty much similar and one of the columns should be removed to avoid duplication of data
df["b 2 r"] = df["Bedroom2"] - df["Rooms"]
df[["b 2 r", "Bedroom2", "Rooms"]].head()
# we can see that the difference is very minimal here that will be wise to 
# remove one of the 2 columns
df = df.drop(["b 2 r", "Bedroom2"],1)

# Check for null values
df.isnull().sum()
# visualizing missing values, the distrubbution of NA in data frame space.
fig, ax = plt.subplots(figsize=(15,7))
sns.heatmap(df.isnull(), yticklabels=False,cmap="viridis")
# Percentage of missing values
df.isnull().sum()/len(df)*100
# From the information above, we can notice that few feature varaibles still have large percentage of 
# missing values. At this point we are ignoring it, but at later state if we will take those as our feature
# variables for our model, we will explore ways to fill in those information or to remove those from our data.
#df = df.drop(["Landsize","BuildingArea","YearBuilt"],axis=1)

# Also since our target variable is price, it makes sense to drop rows for 
# price columns where price values are missing
# Longtitude and Lattitude are critical that should not be null too.
# 34856-->20993
df.dropna(subset=["Price","Longtitude","Lattitude"], inplace=True)
df.shape
# 20993-->9020
df.dropna(subset=["Landsize","BuildingArea","YearBuilt"], inplace=True)
df.shape
# 8887
df2 = df.dropna()

# 这段缺失值处理的程序是Kaggle上的专家提供的，在前面删除了关键值缺失的行后，只有Car列缺失的需要处理
# 不过可以了解一下缺失值处理的一些技术。
# Pre-processing attributes having null values， Cleaning / Filling Missing Data
# =============================================================================
# There are 5 ways to find the null values if present in the dataset

#     isnull() — provides the boolean value for the complete dataset to know if any null value is present or not
#     isna() — same as the isnull() function, provides the same output
#     isna().any() — gives a boolean value if any null value is present or not, but it gives results column-wise, not in tabular format
#     isna().sum() — gives the sum of the null values preset in the dataset column-wise
#     isna().any().sum() — gives output in a single value if any null is present or not

# Imputing techniquess
# 
#     fillna — filling in null values based on given value (mean, median, mode, or specified value)
#     bfill / ffill — stands for backward fill and forward fill (filling in missing values based on the value after or before the column.)
#     Simple Imputer — Sklearn’s built-in function that imputes missing values (commonly used alongside a pipeline when building ML models)
# 
# 
# =============================================================================

# 这一段的变量用均值填充，不过实际没有作用 ======================================
# Mean and Median of values in column 'Price'

print(f"Median : {df['Price'].median()}")
print(f"Mean : {df['Price'].mean()}")

# All occurrences of missing_values are imputed by median Price
price_imputer = SimpleImputer(missing_values = np.nan, strategy='median')
df[['Price']] = price_imputer.fit_transform(df[['Price']])
df['Price'].head(10)

# Checking null values of attribute 'Distance'
df['Distance'].isnull().sum()
df['Distance'].mean()
# Filling null values of attribute 'Distane' using mean 
distance_mean = round(df['Distance'].mean(),1)
df['Distance'].fillna(distance_mean, inplace = True)

# Checking null values of attribute 'Postcode'
df['Postcode'].isnull().sum()
# Counting unique postcodes in column 'Postcode'
df['Postcode'].value_counts()
df['Postcode'].median()
# fillna() replaces null values of attribute 'Postcode' by median
postcode_median = round(df['Postcode'].median())
df['Postcode'].fillna(postcode_median, inplace = True)

'''
# This column is droped already
# value_counts() finds the unique no. of bedroom counts
df['Bedroom2'].value_counts()
# Checking null values in column 'Bedroom2'
df['Bedroom2'].isnull().sum()
# Displaying first 20 values of attribute 'Bedroom2'
print("Bedrooms with NULL values")
df['Bedroom2'].head(20)
# Null values of Bedroom replaced by 0
df['Bedroom2'].fillna(0, inplace= True)
print("Bedrooms after replacing NULL values")
df['Bedroom2'].head(20)
'''

# Checking null values in column 'Bathroom'
df['Bathroom'].isnull().sum()
# Displaying first 20 values of attribute 'Bathroom'
print("Bathroom with NULL values")
df['Bathroom'].head(20)
# Null values of Bathroom replaced by 1
df['Bathroom'].fillna(1, inplace= True)
print("Bathroom after replacing NULL values")
df['Bathroom'].head(20)

# Checking null values in column 'Landsize'
df['Landsize'].isna().sum()
# Mean and Median values of column 'Landsize'
print(f"Median : {df['Landsize'].median()}")
print(f"Mean : {round(df['Landsize'].mean(),0)}")
# Displaying first 20 values of attribute 'Landsize'
print("Landsize with NULL values")
df['Landsize'].head(20)
# All occurrences of missing_values are imputed by median Landsize
from sklearn.impute import SimpleImputer
land_imputer = SimpleImputer(missing_values = np.nan, strategy='median')
df[['Landsize']] = land_imputer.fit_transform(df[['Landsize']])
df['Landsize'].head(20)

# Checking NULL values in column BuildingArea
df['BuildingArea'].isna().sum()
# Mean and Median of values in column 'BuildingArea'
print(f"Median : {df['BuildingArea'].median()}")
print(f"Mean : {round(df['BuildingArea'].mean())}")
# Dosplaying first 20 values of attribute 'BuildingArea'
print("BuildingArea with NULL values")
df['BuildingArea'].head(20)
# All occurrences of missing_values are imputed by mean building area
from sklearn.impute import SimpleImputer
area_imputer = SimpleImputer(missing_values = np.nan, strategy='mean')
df[['BuildingArea']] = land_imputer.fit_transform(df[['BuildingArea']])
df['BuildingArea'].head(20)

# Mean and Median of values in column 'YearBuilt'
df['YearBuilt'].isna().sum()
print(f"Median : {df['YearBuilt'].median()}")
print(f"Mean : {round(df['YearBuilt'].mean())}")
# All occurrences of missing_values are imputed by mean YearBuilt
from sklearn.impute import SimpleImputer
year_imputer = SimpleImputer(missing_values = np.nan, strategy='mean')
df[['YearBuilt']] = land_imputer.fit_transform(df[['YearBuilt']])
df['YearBuilt'].head(20)

# 车位数据缺失的填零============================================================
# Checking null values in column 'Car'
df['Car'].isnull().sum()
# Displaying first 20 values of attribute 'Car'
print("Car with NULL values")
df['Car'].head(20)
# Null values of Car replaced by 0
df['Car'].fillna(0, inplace= True)
print("Car after replacing NULL values")
df['Car'].head(20)


# 这一段用后面的或前面记录的值填充的也没有作用，因为已经没有缺失了。==============
# Displaying first 20 values of 'CouncilArea'
df['CouncilArea'].head(20)
# =============================================================================
# - bfill() :
# 
# It is used to backward fill the missing values in the dataset.
# The missing values are replaced by values in next row of the same column
# =============================================================================
# Appying bfill for NULL values in attribute 'CouncilArea'
df['CouncilArea'].bfill(inplace=True)
df['CouncilArea']
# Checking NULL values in column 'CouncilArea' after bfill
df['CouncilArea'].isnull().sum()

# Checking NULL values in column 'Latitude'
df['Lattitude'].isnull().sum()
# ffill: Forward fill (NULL values are replaced by corresponding value in the previous row)
df['Lattitude'].fillna(method = 'ffill' , inplace=True)
# Checking NULL values in column 'Lattitude' after ffill
df['Lattitude'].isnull().sum()

# Checking NULL values in column 'Longtitude'
df['Longtitude'].isnull().sum()
# ffill: Forward fill (NULL values are replaced by corresponding value in the previous row)
df['Longtitude'].fillna(method = 'ffill' , inplace=True)
# Checking NULL values in column 'Lattitude' after ffill
df['Longtitude'].isnull().sum()

# Checking NULL values in column 'Regionname' 
df['Regionname'].isnull().sum()
# bfill: Backward fill (NULL values are replaced by corresponding value in the next row)
df['Regionname'].bfill(inplace=True)
df['Regionname']
# Checking NULL values in column 'Regionname' after bfill
df['Regionname'].isnull().sum()

# Checking NULL values in column 'Propertycount'
df['Propertycount'].isnull().sum()
# value_counts() finds number of unique properties in each suburb
df['Propertycount'].value_counts()
# NULL values of attribute 'Propertycount' are replaced by ffill
df['Propertycount'].ffill(inplace=True)
# Checking NULL values in column 'Propertycount' after ffill
df['Propertycount'].isnull().sum()

# Now all NULL values of all attributes are replaced ==========================
df.isnull().sum()
df.info()

# Changing Data type
objdtype_cols = df.select_dtypes(["object"]).columns
df[objdtype_cols] = df[objdtype_cols].astype("category")
# looking at data information above, we can notice that "Date" is also converted
# to category.
# in this step we will cast date to datetime
df["Date"] = pd.to_datetime(df["Date"])
df.info()

# Finding Outliers ============================================================
df.describe().T
# From the statstical summary above we can see that max price in our data is nearly $11.2 million. 
# That looks like a clear outlier. But before removing it, lets first ensure that we have very few values
# in that range.
## to findout outliers lets divide data into different price ranges to identify number of occurences of data in different price ranges
df['PriceRange'] = np.where(df['Price'] <= 100000, '0-100,000',  
    np.where ((df['Price'] > 100000) & (df['Price'] <= 1000000), '100,001 - 1M',
    np.where((df['Price'] > 1000000) & (df['Price'] <= 3000000), '1M - 3M',
    np.where((df['Price']>3000000) & (df['Price']<=5000000), '3M - 5M',
    np.where((df['Price']>5000000) & (df['Price']<=6000000), '5M - 6M',
    np.where((df['Price']>6000000) & (df['Price']<=7000000), '6M - 7M',
    np.where((df['Price']>7000000) & (df['Price']<=8000000), '7M-8M', 
    np.where((df['Price']>8000000) & (df['Price']<=9000000), '8M-9M',
    np.where((df['Price']>9000000) & (df['Price']<=10000000), '9M-10M', 
    np.where((df['Price']>10000000) & (df['Price']<=11000000), '10M-11M', 
    np.where((df['Price']>11000000) & (df['Price']<=12000000), '11M-12M', '')
    ))))))))))
                              
df.groupby(["PriceRange"]).agg({"PriceRange": ["count"]})

# Lets drop those outliers of price, 27242
df.drop(df[(df["PriceRange"] == "0-100,000") | 
    (df["PriceRange"] == "7M-8M") | 
    (df["PriceRange"] == "8M-9M") | 
    (df["PriceRange"] == "11M-12M")].
    index, inplace=True)

df.describe().T

df.groupby(["Rooms"])["Rooms"].count()
# drop the outliers in rooms,27233
# df.drop(df[(df["Rooms"] == 12) |(df["Rooms"] == 16)].index,inplace=True)
df.drop(df[df["Rooms"] >8].index,inplace=True)
df.describe().T


# 删除辅助列
df['Distance'] = round(df['Distance'])
df = df.drop(["PriceRange"],axis=1)
df.shape

# Price trend against year per house
## extract year and month from date
df["Year"] = df["Date"].apply(lambda x:x.year)
df['Month']=pd.DatetimeIndex(df['Date']).month

df.head(5)

# 画数值型变量的分布图==========================================================
# have a look at the last dataset we get
# sns.distplot(df, kde=False, bins=20).set(xlabel="Price");
numerics = ["int16", "int32", "int64", "float16", "float32", "float64"]
# df.select_dtypes(include = numerics)
df.select_dtypes(include = numerics).hist(bins=15, figsize=(15, 6),layout=(4,4))

# 画各类房产价格随时间变化的趋势================================================
# data subset by type
# house price
df_h = df[df["Type"]=="h"]
# condo price
df_u = df[df["Type"]=="u"]
# townhouse price
df_t = df[df["Type"]=="t"]
#house, condo and townhouse price groupby "year" and "mean"
df_h_y = df_h.groupby("Year").mean()
df_u_y = df_u.groupby("Year").mean()
df_t_y = df_t.groupby("Year").mean()
df_h_y.head()

# sns.implot(x="Year", y="Price", hue="Type", data=df,
# x_estimator=np.mean);
df_h_y["Price"].plot(kind="line", color="r", label="House")
df_u_y["Price"].plot(kind="line", color="g", label="Condo")
df_t_y["Price"].plot(kind="line", color="b", label="TownHouse")
year_xticks=[2016,2017,2018]
plt.ylabel("Price")
plt.xticks( year_xticks)
plt.title("Melboune price trend VS Year per type")
plt.legend()

df.shape
df.columns

# change  category type into numeric
le=LabelEncoder()
df['Suburb']=le.fit_transform(df.Suburb)
df.Method = le.fit_transform(df.Method)
df.SellerG=le.fit_transform(df.SellerG)
df.Regionname=le.fit_transform(df.Regionname)
df.CouncilArea = le.fit_transform(df.CouncilArea)
# df.Type = le.fit_transform(df.Type)
#convert categorical variable into dummy
df = pd.get_dummies(df, prefix="Type",columns=["Type"])
df.info()
df.columns.values

# 画房价的分布图观察
sns.scatterplot(x='Longtitude',y='Lattitude',data=df,hue='Price')

#histogram
from scipy.stats import norm
sns.distplot(df['Price'], fit=norm);
# It'll be better to transform target variable Price with a log transofrm.
df["LogPrice"] = np.log(df['Price'])
sns.distplot(df["LogPrice"], fit=norm);
#skewness and kurtosis
print("Skewness: %f" % df['Price'].skew())
print("Kurtosis: %f" % df['Price'].kurt())

# Get the fitted parameters used by the function
(mu, sigma) = norm.fit(df["LogPrice"])
print( '\n mu = {:.2f} and sigma = {:.2f}\n'.format(mu, sigma))

#Get also the QQ-plot
from scipy import stats
fig = plt.figure()
res = stats.probplot(np.log(df['LogPrice']), plot=plt)
plt.show()

# 随机重新排序,可以有效提高模型的准确率 ========================================
df = df.sample(frac=1).reset_index(drop=True)  
df.isnull().sum()

# Final dataset
df_NN=df[['Year','YearBuilt','Distance','Lattitude','Longtitude','Propertycount',
          'Landsize','BuildingArea', 'Rooms','Bathroom', 'Car','Type_h','Type_t','Type_u','LogPrice']]
df_NN.isnull().sum()
df_NN.shape

# df_NN.to_csv("D:/temp/data/Melbourne_housing/Melbourne_housing_pre.csv",  encoding="utf-8")

# sns.distplot(df['YearBuilt'], fit=norm);
# sns.distplot(np.log(df['YearBuilt']), fit=norm);
# sns.distplot(df['Distance'], fit=norm);
# sns.distplot(np.log(df['Distance']), fit=norm);
# sns.distplot(df['Lattitude'], fit=norm);
# sns.distplot(np.log(df['Lattitude']), fit=norm);
# sns.distplot(df['Longtitude'], fit=norm);
# sns.distplot(np.log(df['Longtitude']), fit=norm);
# sns.distplot(df['Propertycount'], fit=norm);
# sns.distplot(np.log(df['Propertycount']), fit=norm);
# sns.distplot(df['Landsize'], fit=norm);
# sns.distplot(np.log(df['Landsize']), fit=norm);
# sns.distplot(df['BuildingArea'], fit=norm);
# sns.distplot(np.log(df['BuildingArea']), fit=norm);


# Sample and target, train and test
X=df_NN[['Year','YearBuilt','Distance','Lattitude','Longtitude','Propertycount',
          'Landsize','BuildingArea', 'Rooms','Bathroom', 'Car','Type_h','Type_t','Type_u']]
y=df_NN['LogPrice']
X_train, X_test, y_train, y_test = train_test_split(X,y, test_size = .20, random_state=42)

# Data standardization  零一标准化=============================================
mean = X_train.mean(axis=0)
X_train -= mean
std = X_train.std(axis=0)
X_train /= std
X_test -= mean
X_test /= std

# -----------------------------------------------------------------------------------------
# 线性回归模型是用于比较的基线模型
regressor = LinearRegression()
# Fit model to training data
regressor.fit(X_train,y_train)
# Predict
# Predicting test set results
y_pred = regressor.predict(X_test)
#  0.742346869078488, the original on kaggle is 0.570662925365457, great improvment
# 0.742346869078488
regressor.score(X_test,y_test)
# 0.742346869078488
r2_score(y_test,y_pred)

plt.scatter(y_test, y_pred)
# Histogram of the distribution of residuals
sns.distplot((y_test - y_pred), fit=norm)

cdf = pd.DataFrame(data = regressor.coef_, index = X.columns,columns = ['Coefficients'])
cdf

y_pred_t_o = np.round(np.exp(regressor.predict(X_train)),2)
y_pred_o = np.round(np.exp(y_pred),2)
y_train_o = np.round(np.exp(y_train),2)
y_test_o = np.round(np.exp(y_test),2)
err_t = abs(y_train_o - y_pred_t_o)
mae_lt = sum(err_t)/len(err_t)
err_t2 = abs(y_test_o - y_pred_o)
mae_lt2 = sum(err_t2)/len(err_t2)
# LinearRegression MAE train:  238152.264223516  Accuracy:  0.7810946104912015 MAE test:  252793.69442595684  Test Accuracy:  0.7728025889428027
print("LinearRegression MAE train: ",mae_lt," Accuracy: ",1-mae_lt/y_train_o.mean(),
      "MAE test: ",mae_lt2," Test Accuracy: ",1-mae_lt2/y_test_o.mean())

# 画特征重要性
# https://deephub.blog.csdn.net/article/details/105487021?utm_medium=distribute.pc_relevant.none-task-blog-2%7Edefault%7ECTRLIST%7Edefault-1.no_search_link&depth_1-utm_source=distribute.pc_relevant.none-task-blog-2%7Edefault%7ECTRLIST%7Edefault-1.no_search_link
for i,v in enumerate(regressor.coef_):  
    print('Feature: %0d, Score: %.5f' % (i,v))  
df_importance = pd.DataFrame({"Feature":X_train.columns,"importance":abs(regressor.coef_)})
df_importance.sort_values(["importance"],ascending = False, inplace=True)
plt.bar(df_importance["Feature"], df_importance["importance"])  
plt.xticks(rotation=45)
plt.show() 

# ------------------------------------------------------------------------------------------------
# 随机森林回归模型是更好的机器学习回归模型， https://www.jianshu.com/p/af6b9f15200f
# https://www.kaggle.com/bidiptabikashgogoi/price-prediction-with-88-accuracy-5-model-tested
# Python集成回归模型 https://www.cnblogs.com/Lin-Yi/p/8972051.html
from sklearn.model_selection import GridSearchCV
from sklearn.ensemble import RandomForestRegressor
rf = RandomForestRegressor()
params = {"max_depth":[25,30,35,40], "n_estimators":[42,45,48,51]}
rf_reg = GridSearchCV(rf, params, cv = 10, n_jobs =10)
rf_reg.fit(X_train, y_train)
print(rf_reg.best_estimator_)
regressor_RF = rf_reg.best_estimator_

# from sklearn.ensemble import RandomForestRegressor
# regressor_RF = RandomForestRegressor()
regressor_RF.fit(X_train,y_train)
y_pred_RF = regressor_RF.predict(X_test)
# 0.8468594088054577， Price对数转换后0.8855182522807963, Type作独热编码后0.8926109722380867
regressor_RF.score(X_test,y_test)
# 0.8069878879987716，r2_score稍有不同，稍为低一点。Price对数转换后0.8855182522807963，Type作独热编码后 0.8926109722380867
r2_score(y_test,y_pred_RF)
plt.scatter(y_test, y_pred,c = "blue",label = "Linear")
plt.scatter(y_test, y_pred_RF,c = "green",label = "Random Forest")
plt.legend(loc = "upper left")
plt.show()
sns.distplot((y_test - y_pred_RF), fit = norm)

y_pred_t_RF_o = np.round(np.exp(regressor_RF.predict(X_train)),2)
y_pred_RF_o = np.round(np.exp(y_pred_RF),2)
y_train_o = np.round(np.exp(y_train),2)
y_test_o = np.round(np.exp(y_test),2)
err_t_RF = abs(y_train_o - y_pred_t_RF_o)
mae_lt_RF = sum(err_t_RF)/len(err_t_RF)
err_t2_RF = abs(y_test_o - y_pred_RF_o)
mae_lt2_RF = sum(err_t2_RF)/len(err_t2_RF)
# RandomForestRegressor MAE train:  59602.10845284314  Accuracy:  0.9452147859733556 MAE test:  164940.00928056418  Test Accuracy:  0.8517607681101779
# RandomForestRegressor MAE train:  58412.18957154735  Accuracy:  0.9463085385649727 MAE test:  160344.32230726557  Test Accuracy:  0.8558911250193315
print("RandomForestRegressor MAE train: ",mae_lt_RF," Accuracy: ",1-mae_lt_RF/y_train_o.mean(),
      "MAE test: ",mae_lt2_RF," Test Accuracy: ",1-mae_lt2_RF/y_test_o.mean())



# 画特征重要性
df_importance = pd.DataFrame({"Feature":X_train.columns,"importance":regressor_RF.feature_importances_})
df_importance.sort_values(["importance"],ascending = False, inplace=True)
plt.bar(df_importance["Feature"], df_importance["importance"])  
plt.xticks(rotation=45)
plt.show() 

# --------------------------------------------------------------------------------------------------
from sklearn.model_selection import GridSearchCV
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error

ridge=Ridge()
parameters= {'alpha':[x for x in [0.1,0.2,0.4,0.5,0.7,0.8,1]]}

ridge_reg=GridSearchCV(ridge, param_grid=parameters)
ridge_reg.fit(X_train,y_train)
print("The best value of Alpha is: ",ridge_reg.best_params_)

ridge_mod=Ridge(alpha=1)
ridge_mod.fit(X_train,y_train)
y_pred_Rg_t=ridge_mod.predict(X_train)
y_pred_Rgt2=ridge_mod.predict(X_test)

ridge_mod.score(X_test,y_test)
r2_score(y_test,y_pred_Rgt2)

print('Root Mean Square Error train = ' + str(np.sqrt(mean_squared_error(y_train, y_pred_Rg_t))))
print('Root Mean Square Error test = ' + str(np.sqrt(mean_squared_error(y_test, y_pred_Rgt2))))  

# ---------------------------------------------------------------------------------------------------
from sklearn.linear_model import Lasso

Lasso_reg =Lasso()
parameters= {'alpha':[x for x in [0.0005,0.001,0.01,0.1,1]]}

Lasso_reg=GridSearchCV(Lasso_reg, param_grid=parameters)
Lasso_reg.fit(X_train,y_train)
print("The best value of Alpha is: ",Lasso_reg.best_params_,Lasso_reg.best_score_)

Lasso_reg =Lasso(alpha=0.001)
Lasso_reg.fit(X_train,y_train)
y_pred_Ls_t=Lasso_reg.predict(X_train)
y_pred_Ls_t2=Lasso_reg.predict(X_test)

Lasso_reg.score(X_test,y_test)
r2_score(y_test,y_pred_Ls_t2)

print('Root Mean Square Error train = ' + str(np.sqrt(mean_squared_error(y_train, y_pred_Ls_t))))
print('Root Mean Square Error test = ' + str(np.sqrt(mean_squared_error(y_test, y_pred_Ls_t2)))) 

# --------------------------------------------------------------------------------------------------
from sklearn.model_selection import GridSearchCV
import xgboost as xgb

xgbr = xgb.XGBRegressor()
params = {'learning_rate': [0.18,0.19, 0.2, 0.21], 'max_depth': [4,5,6,7] }

xgbr_reg = GridSearchCV(xgbr, params, cv = 10, n_jobs =1)
xgbr_reg.fit(X_train,y_train)

print("Best params:{}".format(xgbr_reg.best_params_))

best_x = xgbr_reg.best_estimator_
y_train_pred_x = best_x.predict(X_train)
y_val_pred_x = best_x.predict(X_test)

best_x.score(X_test,y_test)
r2_score(y_test, y_val_pred_x)

y_pred_t_XGB_o = np.round(np.exp(y_train_pred_x),2)
y_pred_XGB_o = np.round(np.exp(y_val_pred_x),2)
y_train_o = np.round(np.exp(y_train),2)
y_test_o = np.round(np.exp(y_test),2)
err_t_XGB = abs(y_train_o - y_pred_t_XGB_o)
mae_lt_XGB = sum(err_t_XGB)/len(err_t_XGB)
err_t2_XGB = abs(y_test_o - y_pred_XGB_o)
mae_lt2_XGB = sum(err_t2_XGB)/len(err_t2_XGB)
# XGB Regressor MAE train:  107699.9370125312  Accuracy:  0.9009957364540272 MAE test:  152108.1304596506  Test Accuracy:  0.8633385488133405
# XGB Regressor MAE train:  91652.72750277315  Accuracy:  0.9157472971656799 MAE test:  147101.07134810038  Test Accuracy:  0.8678371378256048
print("XGB Regressor MAE train: ",mae_lt_XGB," Accuracy: ",1-mae_lt_XGB/y_train_o.mean(),
      "MAE test: ",mae_lt2_XGB," Test Accuracy: ",1-mae_lt2_XGB/y_test_o.mean())

# 画特征重要性
df_importance = pd.DataFrame({"Feature":X_train.columns,"importance":best_x.feature_importances_})
df_importance.sort_values(["importance"],ascending = False, inplace=True)
plt.bar(df_importance["Feature"], df_importance["importance"])  
plt.xticks(rotation=45)
plt.show()


# -----------------------------------------------------------------------------------------------
# 堆叠回归模型
# 参与堆叠的回归模型性能：均方差(标准差)，在本数据集gbr模型性能最好，lgbm, xgb,randomforest其次，SVR与Lasso最后
# lightgbm: 0.1702 (0.0101)
# xgboost: 0.1796 (0.0107)
# SVR: 0.2648 (0.0124)
# lasso: 0.2781 (0.0157)
# rf: 0.1868 (0.0099)
# gbr: 0.1635 (0.0101)

from sklearn.model_selection import KFold, cross_val_score, GridSearchCV
from sklearn.metrics import mean_squared_error
from lightgbm import LGBMRegressor
from xgboost import XGBRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import RobustScaler
from sklearn.linear_model import Lasso
from sklearn.svm import SVR
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from mlxtend.regressor import StackingCVRegressor

# Define error metrics, mean_squared_error
def rmsle(y, y_pred):
    return np.sqrt(mean_squared_error(y, y_pred))
# Setup cross validation folds to 12
kf = KFold(n_splits=12, random_state=42, shuffle=True)
# mean_squared_error for k folds cross validation
def cv_rmse(model, X=X_train, y=y_train):
    rmse = np.sqrt(-cross_val_score(model, X, y, scoring="neg_mean_squared_error", cv=kf))
    return (rmse)

# Light Gradient Boosting Regressor
# lightgbm = LGBMRegressor(objective='regression', num_leaves=6, learning_rate=0.01, n_estimators=7000,
#                         max_bin=200, bagging_fraction=0.8, bagging_freq=4, bagging_seed=8, feature_fraction=0.2,
#                         feature_fraction_seed=8, min_sum_hessian_in_leaf = 11, verbose=-1,  random_state=42)
# GridSearch for better hyper parameters, must list all candidates
import time
t1 = time.time()
lgbm = LGBMRegressor(n_estimators=6000)                         #  No n_estimators=6000,  1.1110258102416992
# num_threads =2 and n_jobs=4 is best for this GPU
# lgbm = LGBMRegressor(device='gpu',gpu_use_dp=False, max_bin=15, num_threads =2, n_estimators=6000)         #  No n_estimators=6000,  29.460313081741333
params = {'learning_rate': [0.01,0.05,0.1, 0.15], 'max_depth': [4,5,6,7] }
lgbm_reg = GridSearchCV(lgbm, params, cv = 5, n_jobs=4)
lgbm_reg.fit(X_train,y_train)
t2 = time.time()
print("Time: ",t2-t1)

print("Best params:{}".format(lgbm_reg.best_params_))
lightgbm = LGBMRegressor(n_estimators=6000,learning_rate=0.01, max_depth=5, random_state=42)
lgb_model_full_data = lightgbm.fit(X_train, y_train)
# 0.9655331984491075
print(lgb_model_full_data.score(X_train,y_train))
# 0.9157776047654843
print(lgb_model_full_data.score(X_test,y_test))
# 0.8990574820828033
acc = cross_val_score(lightgbm, X_train, y_train).mean()
print(acc)

# Auto search for better hyper parameters with hyperopt, only need to give a range
from hyperopt import fmin, tpe, hp, Trials
from hyperopt.fmin import generate_trials_to_calculate

space_lgbm = {
    'max_depth': hp.choice('max_depth', range(3, 9)),
    'learning_rate': hp.uniform('learning_rate', 0.005, 0.15),
    'n_estimators': hp.choice('n_estimators', range(1000, 7001))
}
def f_lgbm(params):
    #lgbm = LGBMRegressor(**params)                      # 14.93s/trial
    lgbm = LGBMRegressor(device='gpu', **params)        # 65.93s/trial
    acc = cross_val_score(lgbm, X_train, y_train).mean()
    return -acc

# trials = Trials()
# start searching from the best point of GridSearchCV()
trials = generate_trials_to_calculate([{'max_depth':5-3, 'learning_rate':0.01, 'n_estimators':6000-1000}])
# 1001trial [5:08:22, 18.48s/trial, best loss: -0.8996982601242449]  
t1 = time.time()  
best_lgbm = fmin(f_lgbm, space_lgbm, algo=tpe.suggest, max_evals=10, trials=trials)
t2 = time.time()
# 196.01705384254456
print("Time elapsed: ", t2-t1)

print('best:')
# {'learning_rate': 0.019380653271769414, 'max_depth': 3, 'n_estimators': 1043}
# {'learning_rate': 0.009554352393799865, 'max_depth': 4, 'n_estimators': 3033}
print(best_lgbm)
# verify
params = {'max_depth':3+3,'learning_rate':0.019380653271769414,'n_estimators':1000+1043}
lightgbm = LGBMRegressor(**params)
acc = cross_val_score(lightgbm, X_train, y_train).mean()
# 0.8990738845125381 VS 0.8981369905597092
# 0.8996982601242449
print(acc)
lgb_model_full_data = lightgbm.fit(X_train, y_train)
# 0.9653124065681294 VS 0.9786247184642602
# 0.9682836742625958
print(lgb_model_full_data.score(X_train,y_train))
# 0.9158887247112898 VS 0.9148984602011718
# 0.9152661633121549
print(lgb_model_full_data.score(X_test,y_test))

# XGBoost Regressor
# xgboost = XGBRegressor(learning_rate=0.01, n_estimators=6000, max_depth=4, min_child_weight=0, gamma=0.6,
#                         subsample=0.7, colsample_bytree=0.7, objective='reg:linear', thread=-1,
#                         scale_pos_weight=1, seed=27, reg_alpha=0.00006, random_state=42)
# GridSearch for better hyper parameters, must list all candidates
import time
t1 = time.time()
xgbr = XGBRegressor(n_estimators=6000)
# xgbr = XGBRegressor(tree_method='gpu_hist')
params = {'learning_rate': [0.01,0.05,0.1, 0.15], 'max_depth': [4,5,6,7] }
xgbr_reg = GridSearchCV(xgbr, params, cv = 5)
xgbr_reg.fit(X_train,y_train)
t2 = time.time()
print("Time: ",t2-t1)

print("Best params:{}".format(xgbr_reg.best_params_))
xgboost = XGBRegressor(n_estimators=6000, learning_rate=0.01, max_depth=6, random_state=42)

# Auto search for better hyper parameters with hyperopt, only need to give a range
space_xgb = {
    'max_depth': hp.choice('max_depth', range(3, 9)),
    'learning_rate': hp.uniform('learning_rate', 0.005, 0.15),
    'n_estimators': hp.choice('n_estimators', range(1000, 7001))
}
def f_xgb(params):
    xgbr = XGBRegressor(**params)                              # 32.97s/trial
    # xgbr = XGBRegressor(tree_method='gpu_hist', **params)    # 86.38s/trial
    acc = cross_val_score(xgbr, X_train, y_train).mean()
    return -acc

# trials = Trials()
# start searching from the best point of GridSearchCV()
trials = generate_trials_to_calculate([{'max_depth':6-3, 'learning_rate':0.01, 'n_estimators':6000-1000}])
# 27%|██▋       | 266/1000 [3:27:11<13:59:18, 68.61s/trial, best loss: -0.9018863561867961] 
best_xgb = fmin(f_xgb, space_xgb, algo=tpe.suggest, max_evals=1000, trials=trials)
print('best:')
# {'learning_rate': 0.019380653271769414, 'max_depth': 3, 'n_estimators': 1043}
print(best_xgb)
# verify
params = {'max_depth':3+3,'learning_rate':0.019380653271769414,'n_estimators':1000+1043}
xgboost = XGBRegressor(**params)
acc = cross_val_score(xgboost, X_train, y_train).mean()
# 0.8990738845125381 VS 0.8981369905597092
print(acc)
xgb_model_full_data = xgboost.fit(X_train, y_train)
print(xgb_model_full_data.score(X_train,y_train))
print(xgb_model_full_data.score(X_test,y_test))

# Gradient Boosting Regressor
# gbr = GradientBoostingRegressor(n_estimators=6000, learning_rate=0.01, max_depth=4, max_features='sqrt',
#                                 min_samples_leaf=15, min_samples_split=10, loss='huber', random_state=42)  
# GridSearch for better hyper parameters, must list all candidates
params = {'learning_rate': [0.01,0.05,0.1, 0.15], 'max_depth': [4,5,6,7] }
gbr = GradientBoostingRegressor(n_estimators=6000)
gbr_reg = GridSearchCV(gbr, params, cv = 5, n_jobs =12)
gbr_reg.fit(X_train,y_train)
print("Best params:{}".format(gbr_reg.best_params_))
gbr = GradientBoostingRegressor(n_estimators=6000, learning_rate=0.01, max_depth= 6, random_state=42)

# Auto search for better hyper parameters with hyperopt, only need to give a range
space_gbr = {
    'max_depth': hp.choice('max_depth', range(3, 9)),
    'learning_rate': hp.uniform('learning_rate', 0.005, 0.15),
    'n_estimators': hp.choice('n_estimators', range(1000, 7001))
}
def f_gbr(params):
    gbrr = GradientBoostingRegressor(**params)
    acc = cross_val_score(gbrr, X_train, y_train).mean()
    return -acc

# trials = Trials()
# start searching from the best point of GridSearchCV()
trials = generate_trials_to_calculate([{'max_depth':6-3, 'learning_rate':0.01, 'n_estimators':6000-1000}])
# 100%|██████████| 1000/1000 [2:32:31<00:00,  9.15s/trial, best loss: -0.8990738845125381] 
best_gbr = fmin(f_gbr, space_gbr, algo=tpe.suggest, max_evals=1000, trials=trials)
print('best:')
# {'learning_rate': 0.019380653271769414, 'max_depth': 3, 'n_estimators': 1043}
print(best_gbr)
# verify
params = {'max_depth':3+3,'learning_rate':0.019380653271769414,'n_estimators':1000+1043}
gbr = GradientBoostingRegressor(**params)
acc = cross_val_score(gbr, X_train, y_train).mean()
# 0.8990738845125381 VS 0.8981369905597092
print(acc)
gbr_model_full_data = gbr.fit(X_train, y_train)
print(gbr_model_full_data.score(X_train,y_train))
print(gbr_model_full_data.score(X_test,y_test))

# Random Forest Regressor
# rf = RandomForestRegressor(n_estimators=1200, max_depth=15, min_samples_split=5, min_samples_leaf=5,
#                           max_features=None, oob_score=True, random_state=42)
# GridSearch for better hyper parameters, must list all candidates
rf = RandomForestRegressor(n_estimators=1200)
params = {"max_depth":[10,15,20,25]}
rf_reg = GridSearchCV(rf, params, cv = 5, n_jobs =12)
rf_reg.fit(X_train, y_train)
print(rf_reg.best_estimator_)
rf = RandomForestRegressor(n_estimators=1200, max_depth=25)

# Auto search for better hyper parameters with hyperopt, only need to give a range
space_rf = {
    'max_depth': hp.choice('max_depth', range(3, 41)),
    'n_estimators': hp.choice('n_estimators', range(500, 1501))
}
def f_rf(params):
    rfr = RandomForestRegressor(**params)
    acc = cross_val_score(rfr, X_train, y_train).mean()
    return -acc

# trials = Trials()
# start searching from the best point of GridSearchCV()
trials = generate_trials_to_calculate([{'max_depth':25-3, 'n_estimators':1200-500}])
# 100%|██████████| 1000/1000 [2:32:31<00:00,  9.15s/trial, best loss: -0.8990738845125381] 
best_rf = fmin(f_rf, space_rf, algo=tpe.suggest, max_evals=1000, trials=trials)
print('best:')
# {'learning_rate': 0.019380653271769414, 'max_depth': 3, 'n_estimators': 1043}
print(best_rf)
# verify
params = {'max_depth':3+3,'learning_rate':0.019380653271769414,'n_estimators':1000+1043}
rf = RandomForestRegressor(**params)
acc = cross_val_score(rf, X_train, y_train).mean()
# 0.8990738845125381 VS 0.8981369905597092
print(acc)
rf_model_full_data = rf.fit(X_train, y_train)
print(rf_model_full_data.score(X_train,y_train))
print(rf_model_full_data.score(X_test,y_test))

# Stack up all the models above, optimized using xgboost
# stack_gen = StackingCVRegressor(regressors=(xgboost, lightgbm, svr, lasso, gbr, rf),
stack_gen = StackingCVRegressor(regressors=(xgboost, lightgbm, gbr,rf),             
                                meta_regressor=gbr,  # 用本数据集中性能最好的GBR模型作元数据回归                        
                                use_features_in_secondary=True)

# Lasso Regressor
# GridSearch for better hyper parameters, must list all candidates
lasso =Lasso()
parameters= {'alpha':[x for x in [0.0005,0.001,0.01,0.1,1]]}
Lasso_reg=GridSearchCV(lasso, param_grid=parameters, cv = 5, n_jobs =16)
Lasso_reg.fit(X_train,y_train)
print("The best value of Alpha is: ",Lasso_reg.best_params_,Lasso_reg.best_score_)
lasso =Lasso(alpha=0.0005)

# Auto search for better hyper parameters with hyperopt, only need to give a range
space_lasso = {
    'alpha': hp.uniform('alpha', 0.00001, 1)
}
def f_lasso(params):
    lassor = Lasso(**params)
    acc = cross_val_score(lassor, X_train, y_train).mean()
    return -acc

# trials = Trials()
# start searching from the best point of GridSearchCV()
trials = generate_trials_to_calculate([{'alpha':0.0005}])
# 1001trial [00:29, 33.81trial/s, best loss: -0.7251041347578142]                       
best_lasso = fmin(f_lasso, space_lasso, algo=tpe.suggest, max_evals=1000, trials=trials)
print('best:')
# {'alpha': 1.678147844795433e-05}
print(best_lasso)
# verify
params = {
    'alpha':1.678147844795433e-05}
lasso = Lasso(**params)
acc = cross_val_score(lasso, X_train, y_train).mean()
# 0.7251041347578142 VS 0.7250847913724463
print(acc)
lasso_model_full_data = lasso.fit(X_train, y_train)
# 0.7310543739434121 VS 0.7310454360416583
print(lasso_model_full_data.score(X_train,y_train))
# 0.7360174443304046 VS 0.7360911150385432
print(lasso_model_full_data.score(X_test,y_test))

# Support Vector Regressor
# svr = make_pipeline(RobustScaler(), SVR(C= 20, epsilon= 0.008, gamma=0.0003))
# GridSearch for better hyper parameters, must list all candidates
svr = SVR()
params = {'C': [10,20,30,40], 'gamma': [0.00003,0.0003,0.003,0.03] }
svr_reg = GridSearchCV(svr, params, cv = 5, n_jobs =10)
svr_reg.fit(X_train,y_train)
print("Best params:{}".format(svr_reg.best_params_))
svr = make_pipeline(RobustScaler(), SVR(C= 10, gamma=0.03))

# Auto search for better hyper parameters with hyperopt, only need to give a range
space_svr = {
    'C': hp.choice('C', range(1, 101)),
    'gamma': hp.uniform('gamma', 0.00003, 0.3)
}
def f_svr(params):
    svrr = SVR(**params)
    acc = cross_val_score(svrr, X_train, y_train).mean()
    return -acc

# trials = Trials()
# start searching from the best point of GridSearchCV()
trials = generate_trials_to_calculate([{'C':25-1, 'gamma':0.03}])
# 1001trial [11:09:12, 40.11s/trial, best loss: -0.863839973877513]                         
best_svr = fmin(f_svr, space_svr, algo=tpe.suggest, max_evals=1000, trials=trials)
print('best:')
# {'C': 4, 'gamma': 0.04912516487731497}
print(best_svr)
# verify
params = {'C':4+1,'gamma':0.04912516487731497}
#svr = make_pipeline(RobustScaler(),SVR(**params))
svr = SVR(**params)
acc = cross_val_score(svr, X_train, y_train).mean()
# 0.863839973877513
print(acc)
svr_model_full_data = svr.fit(X_train, y_train)
# 0.9026015169186553
print(svr_model_full_data.score(X_train,y_train))
# 0.8842366528479998
print(svr_model_full_data.score(X_test,y_test))


scores = {}

score = cv_rmse(lightgbm)
print("lightgbm: {:.4f} ({:.4f})".format(score.mean(), score.std()))
scores['lgb'] = (score.mean(), score.std())

score = cv_rmse(xgboost)
print("xgboost: {:.4f} ({:.4f})".format(score.mean(), score.std()))
scores['xgb'] = (score.mean(), score.std())

score = cv_rmse(svr)
print("SVR: {:.4f} ({:.4f})".format(score.mean(), score.std()))
scores['svr'] = (score.mean(), score.std())

score = cv_rmse(lasso)
print("lasso: {:.4f} ({:.4f})".format(score.mean(), score.std()))
scores['lasso'] = (score.mean(), score.std())

score = cv_rmse(rf)
print("rf: {:.4f} ({:.4f})".format(score.mean(), score.std()))
scores['rf'] = (score.mean(), score.std())

score = cv_rmse(gbr)
print("gbr: {:.4f} ({:.4f})".format(score.mean(), score.std()))
scores['gbr'] = (score.mean(), score.std())

print('stack_gen')
stack_gen_model = stack_gen.fit(X_train, y_train)
print(stack_gen_model.score(X_train,y_train))
print(stack_gen_model.score(X_test,y_test))

print('lightgbm')
lgb_model_full_data = lightgbm.fit(X_train, y_train)
print(lgb_model_full_data.score(X_train,y_train))
print(lgb_model_full_data.score(X_test,y_test))
acc = cross_val_score(lightgbm, X_train, y_train).mean()
# 0.8981369905597092
print(acc)

print('xgboost')
xgb_model_full_data = xgboost.fit(X_train, y_train)
print(xgb_model_full_data.score(X_train,y_train))
print(xgb_model_full_data.score(X_test,y_test))

print('RandomForest')
rf_model_full_data = rf.fit(X_train, y_train)
print(rf_model_full_data.score(X_train,y_train))
print(rf_model_full_data.score(X_test,y_test))

print('GradientBoosting')
gbr_model_full_data = gbr.fit(X_train, y_train)
print(gbr_model_full_data.score(X_train,y_train))
print(gbr_model_full_data.score(X_test,y_test))

print('Svr')
svr_model_full_data = svr.fit(X_train, y_train)
print(svr_model_full_data.score(X_train,y_train))
print(svr_model_full_data.score(X_test,y_test))

print('Lasso')
lasso_model_full_data = lasso.fit(X_train, y_train)
print(lasso_model_full_data.score(X_train,y_train))
print(lasso_model_full_data.score(X_test,y_test))
acc = cross_val_score(lasso, X_train, y_train).mean()
# 0.7250847913724463
print(acc)



# Blend models in order to make the final predictions more robust to overfitting
def blended_predictions(X):
    return ((0.01 * lasso_model_full_data.predict(X)) + \
            (0.03 * svr_model_full_data.predict(X)) + \
            (0.08 * gbr_model_full_data.predict(X)) + \
            (0.07 * xgb_model_full_data.predict(X)) + \
            (0.06 * lgb_model_full_data.predict(X)) + \
            (0.05 * rf_model_full_data.predict(X)) + \
            (0.70 * stack_gen_model.predict(np.array(X))))
        
# Get final precitions from the blended model
blended_score = rmsle(y_train, blended_predictions(X_train))
scores['blended'] = (blended_score, 0)
print('RMSLE score on train data:')
print(blended_score)        

y_train_pred_b = blended_predictions(X_train)
y_val_pred_b = blended_predictions(X_test)

y_pred_t_blend_o = np.round(np.exp(y_train_pred_b),2)
y_pred_blend_o = np.round(np.exp(y_val_pred_b),2)
y_train_o = np.round(np.exp(y_train),2)
y_test_o = np.round(np.exp(y_test),2)
err_t_blend = abs(y_train_o - y_pred_t_blend_o)
mae_lt_blend = sum(err_t_blend)/len(err_t_blend)
err_t2_blend = abs(y_test_o - y_pred_blend_o)
mae_lt2_blend = sum(err_t2_blend)/len(err_t2_blend)
# blend Regressor MAE train:  94753.46183166957  Accuracy:  0.913229872246608 MAE test:  137192.88081530773  Test Accuracy:  0.8748618947525433
print("blend Regressor MAE train: ",mae_lt_blend," Accuracy: ",1-mae_lt_blend/y_train_o.mean(),
      "MAE test: ",mae_lt2_blend," Test Accuracy: ",1-mae_lt2_blend/y_test_o.mean())

r2_score(y_test,y_val_pred_b)


        



y_train_pred_s = stack_gen_model.predict(X_train)
y_val_pred_s = stack_gen_model.predict(X_test)

plt.scatter(y_test, y_pred,c = "blue",label = "Linear")
plt.scatter(y_test, y_pred_RF,c = "green",label = "Random Forest")
plt.scatter(y_test, y_val_pred_s, c = "red",label = "Stacking")
plt.title("Regressions on LogPrice")
plt.xlabel("Test values")
plt.ylabel("Predicted values")
plt.legend(loc = "upper left")
plt.show()

sns.distplot((y_test - y_val_pred_s), fit = norm)

stack_gen_model.score(X_test,y_test)
r2_score(y_test,y_val_pred_s)
r2_score(y_train,y_train_pred_s)


y_pred_t_stack_o = np.round(np.exp(y_train_pred_s),2)
y_pred_stack_o = np.round(np.exp(y_val_pred_s),2)
y_train_o = np.round(np.exp(y_train),2)
y_test_o = np.round(np.exp(y_test),2)
err_t_stack = abs(y_train_o - y_pred_t_stack_o)
mae_lt_stack = sum(err_t_stack)/len(err_t_stack)
err_t2_stack = abs(y_test_o - y_pred_stack_o)
mae_lt2_stack = sum(err_t2_stack)/len(err_t2_stack)
# stack Regressor MAE train:  108106.02741091237  Accuracy:  0.9015525943728222 MAE test:  135599.81528182197  Test Accuracy:  0.8734977424046799
# stack Regressor MAE train:  90746.46177204624  Accuracy:  0.9168992675421492 MAE test:  137133.8394620078  Test Accuracy:  0.8749157482982907
print("stack Regressor MAE train: ",mae_lt_stack," Accuracy: ",1-mae_lt_stack/y_train_o.mean(),
      "MAE test: ",mae_lt2_stack," Test Accuracy: ",1-mae_lt2_stack/y_test_o.mean())

    
# ------------------------------------------------------------------------------------------------
# 
# copy to tensor dataset
train_data = X_train.copy()
test_data = X_test.copy()
train_targets = np.reshape(np.array(y_train.copy()),(-1,1))
test_targets =  np.reshape(np.array(y_test.copy()),(-1,1))

train_data.shape
test_data.shape
train_targets

# Preparing the data
# Normalizing the data
mean = train_data.mean(axis=0)
train_data -= mean
std = train_data.std(axis=0)
train_data /= std
test_data -= mean
test_data /= std

from tensorflow import keras
from tensorflow.keras import layers

# -----------------------------------------------------------------------------------------------
# 只有稠密层的神经网络DNN， 神经网络的基础模型，后面会尝试卷积神经网络

# Building your model, only dense layer
def build_model():
    model = keras.Sequential([
        layers.Dense(64, activation="relu"),
        # layers.Dropout(0.5),
        layers.Dense(64, activation="relu"),
        # layers.Dropout(0.5),        
        layers.Dense(1)
    ])
    model.compile(optimizer="rmsprop", loss="mse", metrics=["mae"])
    return model

# Validating your approach using K-fold validation
k = 4
num_val_samples = len(train_data) // k
num_epochs = 100
all_scores = []
for i in range(k):
    print(f"Processing fold #{i}")
    val_data = train_data[i * num_val_samples: (i + 1) * num_val_samples]
    val_targets = train_targets[i * num_val_samples: (i + 1) * num_val_samples]
    partial_train_data = np.concatenate(
        [train_data[:i * num_val_samples],
         train_data[(i + 1) * num_val_samples:]],
        axis=0)
    partial_train_targets = np.concatenate(
        [train_targets[:i * num_val_samples],
         train_targets[(i + 1) * num_val_samples:]],
        axis=0)
    model = build_model()
    model.fit(partial_train_data, partial_train_targets,
              epochs=num_epochs, batch_size=32, verbose=0)
    val_mse, val_mae = model.evaluate(val_data, val_targets, verbose=1)
    all_scores.append(val_mae)

# [251889.0625, 241164.015625, 240743.96875, 230196.28125]    
all_scores
# 240998.33203125
np.mean(all_scores)
# 在boston数据集上是0.8892949929661731
print("Dense layer neural network Accuracy: ",1-np.mean(all_scores)/train_targets.mean())


# Saving the validation logs at each fold
num_epochs = 200
all_mae_histories = []
for i in range(k):
    print(f"Processing fold #{i}")
    val_data = train_data[i * num_val_samples: (i + 1) * num_val_samples]
    val_targets = train_targets[i * num_val_samples: (i + 1) * num_val_samples]
    partial_train_data = np.concatenate(
        [train_data[:i * num_val_samples],
         train_data[(i + 1) * num_val_samples:]],
        axis=0)
    partial_train_targets = np.concatenate(
        [train_targets[:i * num_val_samples],
         train_targets[(i + 1) * num_val_samples:]],
        axis=0)
    model = build_model()
    history = model.fit(partial_train_data, partial_train_targets,
                        validation_data=(val_data, val_targets),
                        epochs=num_epochs, batch_size=32, verbose=1)
    mae_history = history.history["val_mae"]
    all_mae_histories.append(mae_history)

# Building the history of successive mean K-fold validation scores
average_mae_history = [
    np.mean([x[i] for x in all_mae_histories]) for i in range(num_epochs)]

# Plotting validation scores, 迭代超过150次后，MAE的改进很小，收敛很慢。
plt.plot(range(1, len(average_mae_history) + 1), average_mae_history)
plt.xlabel("Epochs")
plt.ylabel("Validation MAE")
plt.show()

# Plotting smoothed validation scores, excluding the first 10 data points
# 将每个数据点的值替换为前面数据点的指数移动平均值
def smooth_curve(points, factor=0.9):
    smoothed_points = []
    for point in points:
        if smoothed_points:
            previous = smoothed_points[-1]
            smoothed_points.append(previous * factor + point * (1 - factor))
        else:
            smoothed_points.append(point)
    return smoothed_points
# drop the 10 points in the front
smooth_mae_history = smooth_curve(average_mae_history[10:])
plt.plot(range(1, len(smooth_mae_history) + 1), smooth_mae_history)
plt.xlabel("Epochs")
plt.ylabel("Validation MAE")
plt.show()

# Building your model, only dense layer
def build_model():
    model = keras.Sequential([
        layers.Dense(64, activation="relu"),
        # layers.Dropout(0.5),
        layers.Dense(64, activation="relu"),
        # layers.Dropout(0.5),        
        layers.Dense(1)
    ])
    model.compile(optimizer="rmsprop", loss="mse", metrics=["mae"])
    return model
# Training the final model
model = build_model()
model.fit(train_data, train_targets,
          epochs=200, batch_size=32, verbose=1)
test_mse_score, test_mae_score = model.evaluate(test_data, test_targets)
# Generating predictions on new data
predictions = model.predict(test_data)
predictions[0]    
test_targets[0]
# plot the predictions, better than LinearRegression
plt.scatter(test_targets, predictions)
# 0.5385328194827406
# 0.8134494671523879
r2_score(y_test,predictions)

train_targets_o = np.round(np.exp(train_targets),2)
test_targets_o = np.round(np.exp(test_targets),2)
predictions_t_o =  np.round(np.exp(model.predict(train_data)),2)
predictions_o = np.round(np.exp(predictions),2)
# 0.6916433392638972
r2_score(train_targets_o,predictions_t_o)
# 0.6408760675521747
r2_score(test_targets_o,predictions_o)

err_t_DNN = abs(train_targets_o - predictions_t_o)
mae_lt_DNN = sum(err_t_DNN)/len(err_t_DNN)
err_t2_DNN = abs(test_targets_o - predictions_o)
mae_lt2_DNN = sum(err_t2_DNN)/len(err_t2_DNN)
# Keras DNN MAE train:  [170840.17254337]  Accuracy:  [0.84402656] MAE test:  [186165.20406094]  Test Accuracy:  [0.82811673]
print("Keras DNN MAE train: ",mae_lt_DNN," Accuracy: ",1-mae_lt_DNN/train_targets_o.mean(),
      "MAE test: ",mae_lt2_DNN," Test Accuracy: ",1-mae_lt2_DNN/test_targets_o.mean())
                         
# --------------------------------------------------------------------------------------------------------
# 变换数据形状以使用一维卷积神经网络CNN
# 结果非常不理想，怎样调优? 一维卷积与二维卷积处理MNIST手写数字数据集的准确率分别可以达到97.91%、 98.74%，证明是可以应用的。
# 只是神经网络架构的问题。输入的一维向量只有14个变量，维数太小？
train_data = np.reshape(np.array(train_data),(len(train_data),14,1))
test_data = np.reshape(np.array(test_data),(len(test_data),14,1))


# Instantiating a small convnet
inputs = keras.Input(shape=(14,1))
x = layers.Conv1D(filters=32, kernel_size=3, activation="relu")(inputs)
x = layers.MaxPooling1D(pool_size=2)(x)
x = layers.Conv1D(filters=64, kernel_size=3, activation="relu")(x)
x = layers.MaxPooling1D(pool_size=2)(x)
# x = layers.Conv1D(filters=128, kernel_size=3, activation="relu")(x)
x = layers.Flatten()(x)
x = layers.Dense(32, activation="relu")(x)
outputs = layers.Dense(1)(x)
model = keras.Model(inputs=inputs, outputs=outputs)
model.compile(optimizer="rmsprop", loss="mse", metrics=["mae"])
# Displaying the model's summary
model.summary()

model.fit(train_data, train_targets, epochs=500, batch_size=64)
test_loss, test_acc = model.evaluate(test_data, test_targets)
# Test accuracy: 0.154， 结果非常不理想
print(f"Test accuracy: {test_acc:.3f}")

# --------------------------------------------------------------------------------------------------------
# 变换数据形状以使用二维卷积神经网络CNN
train_data = np.reshape(train_data,(len(train_data),14))
test_data = np.reshape(test_data,(len(test_data),14))


