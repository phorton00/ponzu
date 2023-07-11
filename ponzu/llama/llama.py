


# -- standard imports 
import pandas as pd
import asyncio

# -- local imports
from ._api import getProtocols_api, getProtocolsData_, getChains_api, getYieldPools_api, getPoolsHistoricalYields_api, getFundamentalsByProtocol_api
from ._api import getStablecoinPrices_api, getStablesList_api, getStablecoinHistory_api, getStablecoinsHistory_

from ._processing import filterProtocols_, processProtocolData_, processFundamentalsByProtocol_, getFundamentalsByChain_, getChainMetrics_, combineTVLandMetrics_, processFundamentalsByChain_
from ._processing import filterYieldPools_, processPoolData_, getYieldsDataframe
from ._processing import buildStablecoinPriceDict_, processStablesList_, processStablesHistory

from ._helpers import remapCategories, run_async
from ._helpers import filterValidStables, removeBadStables

# -- TODO: Pull API out of processing 

class Llama: 
    
  def __init__(self):

    # -- initialize dataframe variables (underscore vars are raw data while non-underscore vars are processed data or filtered dfs) 
    self.protocols_ = getProtocols_api()
    self.protocols = pd.DataFrame()

    self.chains_ = getChains_api()
    self.chains_['name_lower'] = self.chains_['name'].apply(lambda x: x.lower())

    self.tvls_ = pd.DataFrame()
    self.tvls = pd.DataFrame()

    self.fundementals_ = pd.DataFrame()
    self.fundementals = pd.DataFrame()

    self.yields_pools = getYieldPools_api() # -- TODO: google cache and ttl decorate stuff 
    self.yields_ = pd.DataFrame()
    self.yields = pd.DataFrame()

    self.stables_ = pd.DataFrame()
    self.stables = pd.DataFrame()

    self.nfts_ = pd.DataFrame()
    self.nfts = pd.DataFrame()

    # -- define variables 
    self.included_tvl_types = ['borrowed']
    self.excluded_protocol_categories = ['CEX', 'Chain']

    self.default_chains = ['Ethereum', 'Binance', 'Optimism', 'Polygon', 'Arbitrum', 'Avalanche', 'Solana']
    self.default_chains_stables = self.default_chains + ['Tron', 'BSC']
    self.default_chains_stables.remove('Binance')

    self.default_metrics = ['tvl', 'borrowed', 'fees', 'volume', 'revenue']
  
    self.sleep = 0.126    # -- sleep time between requests (in seconds)

  # ==================================================
  # -- Protocols
  # ==================================================
  def getProtocols(self, chains = [], includeMultiChain = True, categories = [], exclude_categories = [], tvl_cutoff = 0):
    protocols_df = filterProtocols_(df = self.protocols_, chains = chains, tvl_cutoff = tvl_cutoff, includeMultiChain = includeMultiChain, categories = categories, exclude_categories = exclude_categories)

    return protocols_df


  # ==================================================
  # -- TVLs
  # ==================================================
  
  def getChainTVL(self, chains = [], includeMultiChain = True, categories = [], exclude_categories = [], tvl_cutoff = 0):
    # -- Returns df of protocol tvl by chain and type with columns: ['date', 'chain', 'protocol', 'category', 'type', 'tvl']
    # ---- > Logic: 1) Set api params to defaults if not provided 2) filter protocol list on params 3) call async api. 4) process/combine data 5) return df

    # -- load default paramaters if none are passed
    chains = chains if len(chains) > 0 else self.default_chains
    exclude_categories = exclude_categories if len(exclude_categories) > 0 else self.excluded_protocol_categories

    # -- filter protocols based on chains and other parameters (will lowercase chains -- future note to change this)
    protocols_df = filterProtocols_(df = self.protocols_, chains = chains, tvl_cutoff = tvl_cutoff, includeMultiChain = includeMultiChain, categories = categories, exclude_categories = exclude_categories)

    # -- get unprocessed tvl data
    protocols = protocols_df['slug'].unique()
    protocol_data = run_async(getProtocolsData_, protocols) 
      
    # -- process data into dataframe
    df = processProtocolData_(protocol_data, chains, self.protocols_)
    self.tvls = df
    
    return df
  
  # ==================================================
  # -- Fundementals
  # ==================================================

  def getFundamentalsByChain(self, chain, metric = 'fees'): 
    # -- confirm protocol is valid
    if chain.lower() not in self.chains_['name_lower'].unique():
      raise ValueError(f'{chain} is not a valid chain')
    
    if metric not in self.default_metrics:
      raise ValueError(f'{metric} is not a valid metric')
    
    # -- get api data 
    df = getFundamentalsByChain_(chain, metric)

    # -- process data
    df = processFundamentalsByChain_(df, chain, metric)

    return df
  
  def getFundamentalsByChains(self, chains = list(), metrics = list()):
    chains = self.default_chain if len(chains) == 0 else chains
    metrics = self.default_metrics if len(metrics) == 0 else metrics

    dfs = []

    for chain in chains:
      for metric in metrics:
        df = self.getFundamentalsByChain(chain, metric)
        dfs.append(df)

    df = pd.concat(dfs)

    return df

  def getFundamentalsByProtocol(self, protocol, metric = 'fees'): 
    # -- confirm protocol is valid
    if protocol not in self.protocols_['slug'].unique():
      raise ValueError(f'{protocol} is not a valid protocol')
    
    if metric not in self.default_metrics:
      raise ValueError(f'{metric} is not a valid metric')
    
    # -- get api data
    data = getFundamentalsByProtocol_api(protocol, metric)

    # -- process data
    df = processFundamentalsByProtocol_(data, metric)

    return df
  
  # TODO - fix this function design. Pull out api calls from processing
  def getChainFundamentals(self, chains = [], metrics = []):
    # -- check validity 
    for metric in metrics:
      if metric not in self.default_metrics:
        metrics.remove(metric)
        raise ValueError(f'{metric} is not a valid metric')
      
    for chain in chains:
      # -- TODO - handle various lower or capitalized inputs 
      #chains = [chain.lower() for chain in chains]
      if chain not in self.default_chains:
        if chain.capitalize() in self.default_chains:
          chains[chains.index(chain)] = chain.capitalize()
        else:
          chains.remove(chain)
          raise ValueError(f'{chain} is not a valid chain')
      
    # -- set defaults if not provided 
    chains = chains if len(chains) > 0 else self.default_chains
    metrics = metrics if len(metrics) > 0 else self.default_metrics

    # -- initialize data store
    metric_df = pd.DataFrame()
    tvl_df = pd.DataFrame()

    # -- get metric data
    metrics_ = [metric for metric in metrics if metric not in ['tvl', 'borrowed']]
    if len(metrics_) > 0:
      metric_df = self.getChainMetrics_(chains = chains, metrics = metrics_, sleep = self.sleep)

    # -- get tvl data
    if 'tvl' in metrics or 'borrowed' in metrics:
      tvl_df = self.getChainTVL(chains = chains)

    # -- merge dataframes
    df = combineTVLandMetrics_(tvl_df, metric_df, metrics)
    self.fundementals = df

    return df

  # ==================================================
  # -- Yields
  # ==================================================

  def getHistoricalYields(self, chains = [], tokens = [], protocols = [], tvl_cutoff = 1000000):

    # -- set defaults if not provided (will take a long time to run. intentially allowed to run without parameters)
    chains = chains if len(chains) > 0 else self.default_chains

    # -- get master pool df 
    yields_data = getYieldPools_api() 
    self.yields_pools = getYieldsDataframe(yields_data) 

    # -- filter master pools 
    pools_df = filterYieldPools_(self.yields_pools, tvl_cutoff = tvl_cutoff, chains = chains, tokens = tokens, protocols = protocols)

    # -- get historical data for each pool
    pool_ids = list(pools_df.pool.unique())
    yields_data = run_async(getPoolsHistoricalYields_api, pool_ids) 

    # -- process data and combine into single df
    yields_df = processPoolData_(yields_data, pools_df)

    # -- set object state
    self.yields = yields_df.copy()

    return yields_df
  
  def getCurrentYieldPools(self): 
    # -- get master pool df 
    yields_data = getYieldPools_api() 
    self.yields_pools = getYieldsDataframe(yields_data) 

    return self.yields_pools


  # ==================================================
  # -- Stables
  # ==================================================
  
  def stablecoinHistory(self, stables = [], chains = [], mcap_threshold = 0): 
    # -- get a list valid of stablecoin objects 
    valid_stables_data = getStablesList_api()
    valid_stables = processStablesList_(valid_stables_data)

    # -- filter valid stables for stables provided or use default stables
    stable_objects = filterValidStables(valid_stables, chains, stables, mcap_threshold)
    stable_objects = removeBadStables(stable_objects)

    # -- retrieve historical stablecoin pricing data
    price_data = getStablecoinPrices_api()
    price_dict = buildStablecoinPriceDict_(price_data)

    # -- get stablecoin history for each stablecoin object 
    stables_data = run_async(getStablecoinsHistory_, stable_objects) 
    stables_df = processStablesHistory(stable_objects, stables_data, price_dict)

    # -- filter df by chains
    if len(chains) > 0:
      #chains = [chain.lower() for chain in chains]
      stables_df = stables_df[stables_df['chain'].isin(chains)]
    
    return stables_df

  def stablecoins(self, stables = [], chains = [], mcap_threshold = 0):
    stablecoin_objects = getStablesList_api()
    stablecoin_objects = processStablesList_(stablecoin_objects)

    # -- filter valid stables for stables provided or use default stables
    stablecoin_objects = filterValidStables(stablecoin_objects, chains, stables, mcap_threshold)

    df = pd.DataFrame(stablecoin_objects)

    return df


