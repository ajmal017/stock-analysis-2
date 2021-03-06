import yaml
import datetime
import dateutil
import pandas as pd
import yfinance as yf
import multiprocessing
from typing import List, Tuple
from dataclasses import dataclass
from stock_analysis.indicator import Indicator
from stock_analysis.data_retrive import DataRetrive
from stock_analysis.utils.logger import logger
from stock_analysis.utils.helpers import get_appropriate_date_momentum
from stock_analysis.utils.formula_helpers import annualized_rate_of_return

yf.pdr_override()
logger = logger()
pd.options.display.float_format = '{:,.2f}'.format


@dataclass
class UnitStrategy:
    """
    Perform general strategy which are indpendant on Unit in nature
    
    Parameters
    ----------
    path : str, optional
        Path to company yaml/json. Either path or
        company_name can be used, by default None
    company_name : List, optional
        List of company name. If path is used then this is obsolete
        as 'path' preside over 'company_name', by default None

    Eg:
    >>>from stock_analysis.unit_strategy import UnitStrategy
    >>>sa = UnitStrategy('./data/company_list.yaml')
    """    
    path: str = None
    company_name: List = None

    def __post_init__(self):
        if self.path is not None:
            with open(self.path, 'r') as f:
                self.data = yaml.load(f, Loader=yaml.FullLoader)
        else:
            self.data = {'company': self.company_name}

    def momentum_strategy(self,
                          end_date: str = 'today',
                          top_company_count: int = 20,
                          save: bool = True,
                          export_path: str = '.',
                          verbosity: int = 1) -> pd.DataFrame:
        """
        The strategy is used to identity stocks which had 'good performance'
        based on desired 'return' duration

        eg
        >>>from stock_analysis import UnitStrategy
        >>>sa = UnitStrategy('./data/company_list.yaml')
        >>>sa.momentum_strategy(end_date='01/06/2020')

        Parameters
        ----------
        end_date : str, optional
            End date of of stock record to retrive.
            Must be in format: dd/mm/yyyy, by default 'today' for current date
        top_company_count : int, optional
            No of top company to retrieve based on
            Annualized return, by default 20
        save : int, optional
            Wether to export to disk, by default True
        export_path : str, optional
            Path to export csv.To be used only if 'save' is True,by default'.'
        verbosity : int, optional
            Level of detail logging,1=< Deatil, 0=Less detail , by default 1

        Returns
        -------
        pd.DataFrame
            Record based on monthly and yearly calculation
        """

        if end_date == 'today':
            end = datetime.datetime.now()
        else:
            end = datetime.datetime.strptime(end_date, '%d/%m/%Y').date()
        start = end - dateutil.relativedelta.relativedelta(years=1)

        with multiprocessing.Pool(multiprocessing.cpu_count() - 1) as pool:
            result = pool.starmap(
                self._parallel_momentum,
                [(company, start, end, verbosity) for company in self.data['company']]
            )
        momentum_df = pd.DataFrame(result)
        momentum_df.dropna(inplace=True)
        momentum_df.sort_values(
            by=['return_yearly'],
            ascending=False,
            inplace=True
        )

        if verbosity > 0:
            logger.debug(
                f"Sample output:\n{momentum_df.head(top_company_count)}")
        if save is True:
            momentum_df.head(top_company_count).to_csv(
                f"{export_path}/momentum_result_{end.strftime('%d-%m-%Y')}_top_{top_company_count}.csv",
                index=False)
            if verbosity > 0:
                logger.debug(
                    f"Saved at {export_path}/momentum_result_{end.strftime('%d-%m-%Y')}_top_{top_company_count}.csv")
        else:
            return momentum_df.head(top_company_count)

    def momentum_with_ema_strategy(self,
                                   end_date: str = 'today',
                                   top_company_count: int = 20,
                                   ema_canditate: Tuple[int, int] = (50, 200),
                                   save: bool = True,
                                   export_path: str = '.',
                                   verbosity: int = 1) -> pd.DataFrame:
        """The strategy is used to identity stocks with 'good performance'
        based on desired 'return' duration and 'exponential moving avg'.

        Parameters
        ----------
        end_date : str, optional
            End date of of stock record to retrive.
            Must be in format: dd/mm/yyyy, by default 'today' for current date
        top_company_count : int, optional
            No of top company to retrieve based on Annualized return,
            by default 20
        ema_canditate : Tuple[int, int], optional
            Period (or days) to calculate EMA, by default (50,200)
        save : int, optional
            Wether to export to disk, by default True
        export_path : str, optional
            Path to export csv.To be used only if 'save' is True,by default'.'
        verbosity : int, optional
            Level of detail logging,1=< Deatil, 0=Less detail , by default 1

        Returns
        -------
        pd.DataFrame
            Record based on monthly and yearly calculation and EMA calculation
        """

        logger.info("Performing Momentum Strategy task")
        momentum_df = self.momentum_strategy(
            end_date=end_date,
            top_company_count=top_company_count,
            save=False,
            verbosity=verbosity
        )
        momentum_df.reset_index(drop=True, inplace=True)

        ind = Indicator(company_name=momentum_df.loc[:, 'company'])
        logger.info(
            f"Performing EMA task on top {top_company_count} company till {end_date}")
        if end_date == 'today':
            cutoff_date = end_date
            save_date = datetime.datetime.now().strftime('%d-%m-%Y')
        else:
            save_date = end_date.replace('/', '-')
            cutoff_date = datetime.datetime.strptime(end_date, '%d/%m/%Y')
            assert isinstance(
                cutoff_date, datetime.datetime), 'Incorrect date type'
        ema_df = ind.ema_indicator(
            ema_canditate=ema_canditate,
            cutoff_date=cutoff_date,
            save=False,
            verbosity=verbosity
        )
        momentum_ema_df = momentum_df.merge(
            ema_df,
            on='company',
            validate='1:1'
        )
        if save is True:
            momentum_ema_df.reset_index(drop=True, inplace=True)
            momentum_ema_df.to_csv(
                f"{export_path}/momentum_ema{ema_canditate[0]}-{ema_canditate[1]}_{save_date}_top_{top_company_count}.csv",
                index=False)
            logger.debug(
                f"Saved at {export_path}/momentum_ema{ema_canditate[0]}-{ema_canditate[1]}_{save_date}_top_{top_company_count}.csv")
            if verbosity > 0:
                logger.debug(
                    f"Sample output:\n{momentum_ema_df.head()}")
        else:
            return momentum_ema_df

    def _parallel_momentum(self, 
                           company: str,
                           start,
                           end,
                           verbosity: int = 1):

        logger.info(
            f"Retriving data for {company}")
        try:
            company_df = DataRetrive.single_company_specific(
                company_name=f"{company}.NS", start_date=start, end_date=end)
            company_df.reset_index(inplace=True)
            ar_yearly = annualized_rate_of_return(
                end_date=company_df.iloc[-1].Close,
                start_date=company_df.iloc[0].Close,
                duration=1
            )  # (company_df.iloc[-30,0] - company_df.iloc[0,0]).days/365)
            ar_monthly = annualized_rate_of_return(
                end_date=company_df.iloc[-1].Close,
                start_date=get_appropriate_date_momentum(
                    company_df, company, verbosity=verbosity)[1],
                duration=(company_df.iloc[-1, 0] - company_df.iloc[-30, 0]).days/30
            )
            monthly_start_date = get_appropriate_date_momentum(
                company_df, company, verbosity=0)[0].strftime('%d-%m-%Y')
        except (IndexError, KeyError, ValueError):
            if verbosity > 0:
                logger.debug(
                    f"Data is not available for: {company}")
            company_df = pd.DataFrame({'Date': [datetime.datetime(1000, 1, 1)] * 30,
                                       'Close': [pd.NA] * 30})
            ar_yearly, ar_monthly, monthly_start_date = pd.NA, pd.NA, pd.NA

        return {'company': company,
                'yearly_start_date': company_df.iloc[0].Date.strftime('%d-%m-%Y'),
                'yearly_start_date_close': company_df.iloc[0].Close,
                'yearly_end_date': company_df.iloc[-1].Date.strftime('%d-%m-%Y'),
                'yearly_end_date_close': company_df.iloc[-1].Close,
                'return_yearly': ar_yearly,
                'monthly_start_date': monthly_start_date,
                'monthly_start_date_close': company_df.iloc[-30].Close,
                'monthly_end_date': company_df.iloc[-1].Date.strftime('%d-%m-%Y'),
                'monthly_end_date_close': company_df.iloc[-1].Close,
                'return_monthly': ar_monthly}
