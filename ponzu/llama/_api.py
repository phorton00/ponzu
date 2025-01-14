
# -- standard imports 
import requests
import pandas as pd 
from datetime import datetime
import time 

import asyncio
import aiohttp

from retry import retry

#sem = asyncio.Semaphore(8)

# -- local imports
from ._helpers import getMetricTypeDefaults, buildStableHistoryAPIinputs

# ==================================================
# -- Protocols + Chains 
# ==================================================

@retry(ValueError, tries=3, delay=3)
def getProtocols_api():
  url = 'https://api.llama.fi/protocols' 

  resp = requests.get(url)
  data = resp.json()

  if type(data) != list:
    raise ValueError('Protocols API did not return list.')
  
  if 'id' not in data[0].keys():
    raise ValueError('Protocols API did not return list.')

  df = pd.DataFrame(data)

  return df 

@retry(ValueError, tries=3, delay=3)
def getChains_api():
  url = 'https://api.llama.fi/v2/chains'

  resp = requests.get(url)
  data = resp.json()

  if type(data) != list:
    raise ValueError('Chains API did not return list.')
  
  if 'tvl' not in data[0].keys():
    raise ValueError('Chains API did not return correct values.')

  df = pd.DataFrame(data)

  return df


# ==================================================
# -- TVLs
# ==================================================

def getProtocol_api(protocol):
  url = f'https://api.llama.fi/protocol/{protocol}'
  resp = requests.get(url)
  data = resp.json()

  return data

async def getProtocol_async_api_ratelimt(session, sem, protocol):
  calls = 0 
  call_limit  = 10

  for i in range(call_limit):
    calls += 1
    try:
      data = await getProtocol_async_api(session, sem, protocol)
      if 'data' in data.keys():
        data = data['data']
        break
    except:
      await asyncio.sleep(3)
  
  if calls == call_limit:
    raise ValueError('Protocol Async API did not return dict.')
  
  return data

#@retry(ValueError, tries=5, delay=3)
async def getProtocol_async_api(session, sem, protocol):
  url = f'https://api.llama.fi/protocol/{protocol}'
  async with sem:
    async with session.get(url) as resp:
      try:
        data = await resp.json()
      except:
        print(f'Error: {protocol} - {resp.status} - {resp.text}')
        data = {'chainTvls':{}}

      #if resp.status == 200:
        #data = await resp.json()
      #else:
        #data = await getProtocol_async_api_ratelimt(session, sem, protocol)
         
  if type(data) != dict:
    raise ValueError('Protocol Async API did not return dict.')
  
  if 'chainTvls' not in data.keys():
    raise ValueError('Protocol Async API did not return correct values.')
    
  data = {'protocol': protocol, 'data': data}

  return data

async def getProtocolsData_(protocols, sleep = 0.1): 
  sem = asyncio.Semaphore(8)

  async with aiohttp.ClientSession() as session:
    data = []
    for protocol in protocols:
      # -- new code 
      #try:
        #protocol_data = asyncio.ensure_future(getProtocol_async_api(session, sem, protocol))
      
        #if type(protocol_data['data']) == dict:
          #if 'chainTvls' in protocol_data['data'].keys():
            #data.append(protocol_data)

      #except:

        #await asyncio.sleep(10)

        #protocol_data = asyncio.ensure_future(getProtocol_async_api(session, sem, protocol))
      
        #if type(protocol_data['data']) == dict:
          #if 'chainTvls' in protocol_data['data'].keys():
            #data.append(asyncio.ensure_future(protocol_data))
          
      
        

      # -- used to have a try, except here but trying to avoid that
      data.append(asyncio.ensure_future(getProtocol_async_api(session, sem, protocol)))

      #await asyncio.sleep(0.126)
    
    protocol_data = await asyncio.gather(*data)

  return protocol_data

# ==================================================
# -- Fundamental Metrics
# ==================================================
@retry(ValueError, tries=5, delay=3)
def getFundamentalsByChain_api(chain, metric = 'fees'):
  # -- get metric and metric type
  metric, metric_type = getMetricTypeDefaults(metric)

  # -- build url
  url = f'https://api.llama.fi/overview/{metric_type}/{chain}?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=false&dataType={metric}'

  # -- call url
  resp = requests.get(url)
  data = resp.json()

  return data 

@retry(ValueError, tries=5, delay=3)
def getFundamentalsByProtocol_api(protocol, metric = 'fees'):
  # -- get metric and metric type
  metric, metric_type = getMetricTypeDefaults(metric)

  vol_url_filters = 'excludeTotalDataChart=true&excludeTotalDataChartBreakdown=false&' if metric_type == 'dexs' else ''

  # -- build url
  url = f'https://api.llama.fi/summary/{metric_type}/{protocol}?{vol_url_filters}dataType={metric}'

  # -- call url
  resp = requests.get(url)
  data = resp.json()

  return data


# ==================================================
# -- Stables
# ==================================================


def getStablecoinPrices_api(): 
  url = 'https://stablecoins.llama.fi/stablecoinprices'
  resp = requests.get(url)
  data = resp.json()

  return data

def getStablesList_api(): 
  url = f'https://stablecoins.llama.fi/stablecoins?includePrices=true'
  resp = requests.get(url)
  data = resp.json()

  return data

def getStablecoinHistory_api_(stable_id):
  url = f'https://stablecoins.llama.fi/stablecoin/{stable_id}'

  resp = requests.get(url)
  data = resp.json()

  return data

@retry(ValueError, tries=3, delay=5)
async def getStablecoinHistory_api(session, sem, stable_id):
  url = f'https://stablecoins.llama.fi/stablecoin/{stable_id}'

  async with sem:
    async with session.get(url) as resp:
      try:
        data = await resp.json()
      except:
        print(f'Error: {stable_id} - {resp.status} - {resp.text}')
        data = {'chainBalances':{}}

      #data = await resp.json()

  data_ = {'stable_id': stable_id,'data': data}

  if type(data_['data']['chainBalances']) != dict:
    raise ValueError('Stablecoins API returned an error. Please check your inputs and try again.')

  return data_

async def getStablecoinsHistory_(stables): 
  sem = asyncio.Semaphore(8)

  async with aiohttp.ClientSession() as session:
    data = []
    for stable in stables:
      stable_id = stable['id']

      data.append(
        asyncio.ensure_future(getStablecoinHistory_api(session, sem, stable_id))
      )
    
    stablecoin_data = await asyncio.gather(*data)

    if type(stablecoin_data) != list:
      raise ValueError('Stablecoin History API did not return list.')

  return stablecoin_data

@retry(ValueError, tries=3, delay=5)
async def getStablecoinChartHistory_api(session, sem, chain, stable_id):
  url = f'https://stablecoins.llama.fi/stablecoincharts/{chain}?stablecoin={stable_id}'

  async with sem:
    async with session.get(url) as resp:
      try:
        data = await resp.json()
      except:
        print(f'Error: {stable_id} - {resp.status} - {resp.text}')
        data = []

      #data = await resp.json()

  data_ = {'stable_id': stable_id, 'chain': chain, 'data': data}

  if type(data_['data']) != list:
    raise ValueError('Stablecoins Chart API returned an error. Please check your inputs and try again.')

  return data_

async def getStablecoinsChartHistory_(inputs = []): 

  sem = asyncio.Semaphore(8)

  async with aiohttp.ClientSession() as session:
    data = []
    for input_ in inputs:

      data.append(
        asyncio.ensure_future(getStablecoinChartHistory_api(session, sem, input_['chain'], input_['stable_id']))
      )
    
    stablecoin_data = await asyncio.gather(*data)

    if type(stablecoin_data) != list:
      raise ValueError('Stablecoin Chart History API did not return list.')

  return stablecoin_data






# ==================================================
# -- Yields
# ==================================================

@retry(ValueError, tries=3, delay=3)
def getYieldPools_api(): 
  url = 'https://yields.llama.fi/pools'

  resp = requests.get(url)
  data = resp.json()

  if 'data' not in data.keys():
    raise ValueError('Yields API returned an error. Please check your inputs and try again.')

  return data

#@retry(ValueError, tries=3, delay=5)
async def getYieldHistorical_async(session, sem, pool_id): 
  url = f'https://yields.llama.fi/chart/{pool_id}'

  async with sem:
    async with session.get(url) as resp:
      try:  
        data = await resp.json()
      except:
        print(f'Error: {pool_id} - {resp.status} - {resp.text}')
        data = {'pool_id': pool_id, 'data': None}


  data = {'pool_id': pool_id, 'data': data}

  if type(data['data']['data']) != list :
    print('data type not list: ' + url)
    raise ValueError('Yields API returned an error. Please check your inputs and try again.')

  return data

async def getPoolsHistoricalYields_api(pool_ids, sleep = 0.128): 
  sem = asyncio.Semaphore(8)

  async with aiohttp.ClientSession() as session:
    data = []
    for pool_id in pool_ids:
      data.append(asyncio.ensure_future(getYieldHistorical_async(session, sem, pool_id)))
      #time.sleep(sleep)
    
    pool_data = await asyncio.gather(*data, return_exceptions=True)
    #pool_data = await asyncio.gather(*data)

  if type(pool_data) != list:
    raise ValueError('Pools API did not return list.')

  return pool_data

# ==================================================
# -- Raises
# ==================================================



# ==================================================
# -- NFTs
# ==================================================



# ==================================================
# -- Treasury
# ==================================================



# ==================================================
# -- Costs 
# ==================================================

