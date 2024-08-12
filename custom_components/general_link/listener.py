import socket
import json
import logging
import asyncio
from typing import Any
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_ADDRESS
from .const import CONF_ENVKEY,MANUAL_FLAG,CONF_PLACE
from cryptography.fernet import Fernet
from homeassistant.helpers.storage import Store


_LOGGER = logging.getLogger(__name__)


async def decrypt_message(hass,encrypted_message):
    store = Store(hass, 1, 'secret_key')
    keyload = await store.async_load()
    if not keyload:
        key = Fernet.generate_key().decode()
        await store.async_save(key)
        keyload = await store.async_load()
        _LOGGER.warning("新秘钥 %s", keyload)
        return keyload
    f = Fernet(keyload)
    #encrypted_password = f.encrypt(password_bytes).decode()
    try:
     encrypted_message_bytes = encrypted_message.encode()
    #decrypted_message = await hass.async_add_executor_job(f.decrypt(encrypted_message).decode())
     decrypted_message = f.decrypt(encrypted_message_bytes).decode()
     return decrypted_message
    except Exception :
     return keyload

# 异步收发UDP广播消息
async def _async_send_receive_udp_broadcast(hass : HomeAssistant,data: dict,port: int , dest_address = None ,dest_port: int = 9451,timeout: float = 1.0) -> dict:
    #loop = asyncio.get_running_loop()
    #global data_dict

    # 创建一个UDP套接字
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    # 设置套接字为广播类型
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    # 设置超时时间以避免无限阻塞
    sock.settimeout(timeout)

    # 绑定到所有网络接口和指定的端口
    sock.bind(("", port))
    data_str = json.dumps(data)
    data_bytes = data_str.encode('utf-8')
    if dest_address is not None:
        send_address = dest_address
    else:
        broadcast_address = '<broadcast>'
        send_address = broadcast_address
        

    
    _LOGGER.warning("send_address %s", send_address)
    
    # 发送数据
    
    try:
        while True:
            hass.async_add_executor_job(sock.sendto(data_bytes, (send_address, dest_port)))
            data,addr =  await hass.async_add_executor_job(sock.recvfrom, 1024)
            data_str = data.decode('utf-8')
            data_dict = json.loads(data_str)
            #_LOGGER.warning("data_dict1 %s", data_dict)
            return data_dict
    except socket.timeout:
        _LOGGER.warning("Timeout occurred while receiving data.")
    except Exception as e:
        _LOGGER.error("Error in receiving data: %s", e)
    finally:
        sock.close()
    
    return None

# 主函数
async def sender_receiver(hass : HomeAssistant , userid: str, password: str, placeid: str, port:int = 9999 ,dest_address = None ) -> dict:
    data = {"act": 1, "usr": userid ,"place": placeid}
    if len(password) > 20:
        password = await decrypt_message(hass,password)
        if len(password) > 40:
            return password 
            
    connection = {
        "name": "",
        "broker": "",
        "port": 0,
        "username": "",
        "password": password,
        "protocol": "3.1.1",
        "keepalive": 60
    }

    try:
        #重复3次发送udp广播接收数据
        for _ in range(3):
            await asyncio.sleep(2)
            data_dict = await _async_send_receive_udp_broadcast(hass, data , port , dest_address = dest_address )
            if data_dict is not None:
                break
        
    except Exception as e:
        _LOGGER.error("Error in sender_receiver: %s", e)
   # 判断下connection是否为空 
           # 确保接收到的数据不为空
    if data_dict is not None:
          place = data_dict.get('place')
          host = data_dict.get('host')
          port = data_dict.get('port')
          username = data_dict.get('username')
          connection["name"] = f"IoT_Gateway-{place}"
          connection["broker"] = host
          connection["port"] = port
          connection["username"] = username
          connection[CONF_PLACE] = place
          #connection[MANUAL_FLAG] = True
          connection[CONF_ENVKEY] = userid
          connection[CONF_ADDRESS] = dest_address

          #_LOGGER.warning("data_dict %s", data_dict)
          return connection
         
    else:
          return None
   
