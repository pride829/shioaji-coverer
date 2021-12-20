def shioaji_login():
    import os
    from pathlib import Path
    ca_path = os.path.abspath("./Sinopac.pfx")
    import json
    import shioaji as sj
    account_info = 'account/account_info.json'
    with open(account_info, newline='') as jsonfile:
        account_data = json.load(jsonfile)
    api = sj.Shioaji(simulation=False) 
    print(f'正在使用{account_data["person_id"]}的ID登入...')
    api.login(
        person_id = account_data['person_id'],
        passwd = account_data['passwd'], 
        contracts_cb=lambda security_type: print(f"{repr(security_type)} fetch done.")
    )
    
    print(f'正在啟用位於{ca_path}的憑證...')
    activate = api.activate_ca(ca_path=ca_path, ca_passwd=account_data['ca_passwd'], person_id=account_data['person_id'])
    
    return api