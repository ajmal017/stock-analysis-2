import os
import yaml
import datetime
import dateutil
import pandas as pd
from stock_analysis.utils.logger import logger
from stock_analysis.data_retrive import DataRetrive
from typing import List, Union, Tuple
now_strting = datetime.datetime.now().strftime('%d-%m-%Y')

import yfinance as yf
yf.pdr_override()

logger = logger()

class Indicator:
    
    def __init__(self, path: str):
        
        self.path = path

        if 'yaml' in os.path.split(self.path)[-1]:
            with open(self.path, 'r') as f:
                self.data = yaml.load(f, Loader=yaml.FullLoader)
        
    def volume_indicator_n_days(self, duration: int=90, 
                                export_path: str='.',
                                verbosity: int=1):
        
        end = datetime.datetime.now()
        start = end - dateutil.relativedelta.relativedelta(days=duration)
        vol_ind_df = pd.DataFrame(columns=['company','current date' ,'start date','current volume','mean volume','action'])
        for idx,company in  enumerate(self.data['company']):
            logger.info(f"Retriving data {idx + 1} out of {len(self.data['company'])} for {company}")
            company_df = DataRetrive.single_company_specific(company_name=f"{company}.NS", start_date=start, end_date=end)
            buy_stock = company_df.iloc[-1].Volume > company_df['Volume'].mean()
            vol_ind_df = vol_ind_df.append({'company':company,
                                            'current date':company_df.index[-1].strftime('%m-%d-%Y'),
                                            'start date':company_df.index[0].strftime('%d-%m-%Y'),
                                            'current volume':company_df.iloc[-1].Volume,
                                            'mean volume':company_df['Volume'].mean(),
                                            'close price':company_df.iloc[-1].Close,
                                            'action':buy_stock},
                                        ignore_index=True)
        
        if verbosity > 0:
            logger.info(f"Here are sample 5 company\n{vol_ind_df.head()}\n remaining can be viewed at exported path")
        # vol_ind_df_true['company'].to_csv(f'{export_path}/VolumeIndicator90Days_{now_strting}.csv', index=False)
        vol_ind_df.to_csv(f"{export_path}/VolumeIndicator90Days_detailed_{now_strting}.csv", index=False)
        
    def ema_indicator(self,export_path: str='.',
                        verbosity: int=1):
        
        invalid = []
        ema_indicator_df = pd.DataFrame(columns=['company','ema50', 'ema200','action'])
        for idx,company in  enumerate(self.data['company']):
            logger.info(f"Retriving data {idx + 1} out of {len(self.data['company'])} for {company}")
            company_df = DataRetrive.single_company_complete(company_name=f"{company}.NS")
            if company_df['Close'].isnull().sum() !=0:
                logger.warning(f"{company} have some missing value, fixing it")
                company_df.dropna(inplace=True)
            try:
                ema50 = self._exponential_moving_avarage(data=company_df['Close'], 
                                                        period=50)
                ema200 = self._exponential_moving_avarage(data=company_df['Close'],
                                                        period=200)
                if ema50 > ema200:
                    action = 'buy'
                else:
                    action = 'sell'
                ema_indicator_df = ema_indicator_df.append({'company': company,
                                                            'ema50':ema50, 
                                                            'ema200': ema200,
                                                            'action':action},
                                                        ignore_index=True)
            except Exception as e:
                print(company,e)
                invalid.append(company)
                logger.warning(f"{', '.join(invalid)} has less record than minimum rexquired")
                
        ema_indicator_df.to_csv(f"{export_path}/ema_indicator_{now_strting}.csv", index=False)
        if verbosity > 0:
            logger.debug(f"Saving at {export_path}/ema_indicator_{len(self.data['company'])}company_{now_strting}.csv")

    
    @staticmethod
    def _exponential_moving_avarage( data: Union[pd.Series,List],
                                     period:int,
                                     smoothing_factor: int=2)-> float:
        """Calculate exponential moving avarage based on given period

        Parameters
        ----------
        data : Union[pd.Series,List]
            Data to calculate ema
        period : int
            Period for which ema has to be calculated
        smoothing_factor : int, optional
            Smoothing factor which will be used to calculate Multiplying factor, by default 2

        Returns
        -------
        float
            ema value
        """
        # Calculating multiplying factor
        mf = smoothing_factor/(1 + period)

        # Calculating first SMA
        sma0 = (sum(data[:period])) / period

        # Calculating first EMA
        ema0 = (data[period] * mf) + (sma0 * (1 - mf))

        # Calculating latest EMA
        ema_pre = ema0

        for idx in range(1, len(data)-50):
            ema = (data[idx + 50] * mf) + (ema_pre * (1 - mf))
            ema_pre = ema
            if idx == (len(data) - 50):
                break
        return ema