from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackContext,
    ApplicationBuilder
) 
import json
import os
from dotenv import load_dotenv
from web3 import Web3 , Account
import asyncio
import time
RPC = "https://api.baobab.klaytn.net:8651/"
w3 = Web3(Web3.HTTPProvider(RPC))
load_dotenv()
with open("abi/DexFactory.json", "r") as read_file:
   swap_factory_abi = json.load(read_file)
with open("abi/DexPair.json", "r") as read_file:
   dex_pair_abi = json.load(read_file)
with open("abi/KIP7.json", "r") as read_file:
   kip7_abi = json.load(read_file)
with open("abi/DexRouter.json", "r") as read_file:
   dex_router_abi = json.load(read_file)
bot_key = os.getenv('BOT_TOKEN')
dex_pair = w3.to_checksum_address(os.getenv('BAOBAB_PAIR'))
swap_factory = w3.to_checksum_address(os.getenv('BAOBAB_FACTORY'))
dex_router = w3.to_checksum_address(os.getenv('BAOBAB_ROUTER'))
contract_swap = w3.eth.contract(address=dex_router, abi=dex_router_abi)
contract_factory = w3.eth.contract(address=swap_factory, abi=swap_factory_abi)
private_key = os.getenv('PRIVATE_KEY')
account = Account.from_key(private_key)


async def totalPair():
    pair_count = contract_factory.functions.allPairsLength().call()
    with open("lib/token/pairs.json", 'r') as j:
      pairs_info = json.loads(j.read())
      tokens_list = []
      for pair in pairs_info:
         tokens_list.append(pair["symbol"])
    return pair_count , tokens_list

async def sendtotalPair(update: Update, callback: CallbackContext):
    total, token_list = await totalPair()
    message = f"Total Pair {total}:\n"
    for token in token_list:
        message += f"{token}\n"
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

async def listPair(totalPair):
   pairs = []
   for i in range(totalPair):
      pair_address = contract_factory.functions.allPairs(i).call()
      pairContract = w3.eth.contract(address=pair_address,abi=dex_pair_abi)
      reserves = pairContract.functions.getReserves().call()
      token0_address = pairContract.functions.token0().call()
      token1_address = pairContract.functions.token1().call()
      token0 = w3.eth.contract(address=token0_address, abi=kip7_abi)
      token0_symbol = token0.functions.symbol().call()
      token1 = w3.eth.contract(address=token1_address,abi=kip7_abi)
      token1_symbol = token1.functions.symbol().call()
      pair_info = {
         "pair_address": pair_address,
         "token0": {
               "address": token0_address,
               "symbol": token0_symbol
         },
         "token1": {
               "address": token1_address,
               "symbol": token1_symbol
         }
      }
      pairs.append(pair_info)
   with open('lib/token/pairs.json', 'w') as json_file:
      json.dump(pairs, json_file, indent=4)
      return totalPair

async def updatelistPair(update: Update, callback: CallbackContext):
    # Will be upgrade in future
    pair_count = await totalPair()
    await update.message.reply_text("Done")

async def updatelistPair(update: Update, callback: CallbackContext):
    pair_count = await totalPair()
    listPair(pair_count)
    await update.message.reply_text("Done")


async def swapKlay(update: Update, callback: CallbackContext):
   tokenSwap = (update.message.text).split()
   if tokenSwap[0] == "/swapKlay":
      with open("lib/token/pairs.json", 'r') as j:
         pairs_info = json.loads(j.read())
         for pair in pairs_info:
            if pair["symbol"] == tokenSwap[1]:
               deadline = int(time.time()) + 600 
               pairContract = w3.eth.contract(address=w3.to_checksum_address(pair["pair_address"]),abi=dex_pair_abi)
               reserves = pairContract.functions.getReserves().call()
               wklay = w3.eth.contract(address=w3.to_checksum_address(pair["token0"]["address"]), abi=kip7_abi)
               token1 =  w3.eth.contract(address=w3.to_checksum_address(pair["token1"]["address"]), abi=kip7_abi)
               amount_in = w3.to_wei(tokenSwap[2], "ether")
               tx = wklay.functions.deposit().build_transaction({
                     'chainId': 1001,
                     'gas': 2000000,
                     "maxPriorityFeePerGas": 250000000000,
                     "maxFeePerGas": 250000000000,
                     'nonce': w3.eth.get_transaction_count(account.address),
                     'value': amount_in, 
               })
               signed_transaction = w3.eth.account.sign_transaction(tx, private_key)
               tx_hash = w3.eth.send_raw_transaction(signed_transaction.rawTransaction)
               tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
               print(f"tx hash: {Web3.to_hex(tx_hash)}")
               approve_tx = wklay.functions.approve(dex_router, 2**256-1).build_transaction({
                  'gas': 30000000,  
                  "maxPriorityFeePerGas": 250000000000,
                  "maxFeePerGas": 250000000000,
                  "nonce": w3.eth.get_transaction_count(account.address),
               })   

               raw_transaction = w3.eth.account.sign_transaction(approve_tx, account.key).rawTransaction
               tx_hash = w3.eth.send_raw_transaction(raw_transaction)
               tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
               if tx_receipt["status"] == 1:
                  print(f"approve transaction send for unlimited amount")
               swap_tx = contract_swap.functions.swapExactKLAYForTokens(
                  0,
                  [w3.to_checksum_address(pair["token0"]["address"]),w3.to_checksum_address(pair["token1"]["address"])],
                  account.address,
                  deadline
               ).build_transaction(
                  {
                  'chainId': 1001,
                  'gas': 3000000,
                  "maxPriorityFeePerGas":250000000000,
                  "maxFeePerGas": 250000000000,  
                  'nonce': w3.eth.get_transaction_count(account.address),
                  "value": w3.to_wei(tokenSwap[2],"ether")
                  }
               )
               raw_transaction = w3.eth.account.sign_transaction(swap_tx, account.key).rawTransaction
               print(f"raw transaction: {swap_tx}")
               tx_hash = w3.eth.send_raw_transaction(raw_transaction)
               tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
               print(f"tx hash: {Web3.to_hex(tx_hash)}")
               url = "https://baobab.klaytnscope.com/tx/" + Web3.to_hex(tx_hash) + "?tabId=tokenTransfer"
               keyboard = [[InlineKeyboardButton("View Transaction", url=url)]]
               reply_markup = InlineKeyboardMarkup(keyboard)
               token0_balance = wklay.functions.balanceOf(account.address).call()
               token1_balance = token1.functions.balanceOf(account.address).call()
               balance_account = f"U have \n{pair['token0']['symbol']} : {w3.from_wei(token0_balance, 'ether')} \n{pair['token1']['symbol']} : {w3.from_wei(token1_balance, 'ether')}"
               quote = contract_swap.functions.quote(
                  w3.to_wei(tokenSwap[2],"ether"),
                  reserves[0],
                  reserves[1]
               ).call()
               quoteformat = w3.from_wei(quote,'ether')
               message = "U have received : " + str(quoteformat) + " " + pair["token1"]["symbol"] 
               await update.message.reply_text(message , reply_markup=reply_markup)
               await update.message.reply_text(balance_account)

async def swapToken(update: Update, callback: CallbackContext):
   tokenSwap = (update.message.text).split()
   if tokenSwap[0] == "/swapToken":
      with open("lib/token/pairs.json", 'r') as j:
         pairs_info = json.loads(j.read())
         for pair in pairs_info:
            if pair["symbol"] == tokenSwap[1]:
               deadline = int(time.time()) + 600 
               token0_contract = w3.eth.contract(address=w3.to_checksum_address(pair["token0"]["address"]), abi=kip7_abi)
               token1 =  w3.eth.contract(address=w3.to_checksum_address(pair["token1"]["address"]), abi=kip7_abi)
               token0_balance = token0_contract.functions.balanceOf(account.address).call()
               token1_balance = token1.functions.balanceOf(account.address).call()
               amount_in = w3.to_wei(tokenSwap[2], "ether")
               approve_tx = token0_contract.functions.approve(dex_router, 2**256-1).build_transaction({
                  'gas': 30000000,  
                  "maxPriorityFeePerGas": 250000000000,
                  "maxFeePerGas": 250000000000,
                  "nonce": w3.eth.get_transaction_count(account.address),
               })   
               raw_transaction = w3.eth.account.sign_transaction(approve_tx, account.key).rawTransaction
               tx_hash = w3.eth.send_raw_transaction(raw_transaction)
               tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
               if tx_receipt["status"] == 1:
                  print(f"approve transaction send for unlimited amount")
               swap_tx = contract_swap.functions.swapExactTokensForKLAY(
                  w3.to_wei(tokenSwap[2],"ether"),
                  token0_balance,
                  [w3.to_checksum_address(pair["token0"]["address"]),w3.to_checksum_address(pair["token1"]["address"])],
                  account.address,
                  deadline
               ).build_transaction(
                  {
                  'chainId': 1001,
                  'gas': 3000000,
                  "maxPriorityFeePerGas":250000000000,
                  "maxFeePerGas": 250000000000,  
                  'nonce': w3.eth.get_transaction_count(account.address),
                  "value": 0
                  }
               )
               raw_transaction = w3.eth.account.sign_transaction(swap_tx, account.key).rawTransaction
               print(f"raw transaction: {swap_tx}")
               tx_hash = w3.eth.send_raw_transaction(raw_transaction)
               tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
               print(f"tx hash: {Web3.to_hex(tx_hash)}")
               url = "https://baobab.klaytnscope.com/tx/" + Web3.to_hex(tx_hash) + "?tabId=tokenTransfer"
               keyboard = [[InlineKeyboardButton("View Transaction", url=url)]]
               reply_markup = InlineKeyboardMarkup(keyboard)
               message = "U have received : " + pair["token1"]["symbol"] 
               await update.message.reply_text(message , reply_markup=reply_markup)

if __name__ == '__main__':
    application = ApplicationBuilder().token(bot_key).build()
    application.add_handler(CommandHandler('totalPair', sendtotalPair))
    application.add_handler(CommandHandler('updatelistPair', updatelistPair))
    application.add_handler(CommandHandler('swapKlay', swapKlay))
    application.add_handler(CommandHandler('swapToken', swapToken))
    application.run_polling()