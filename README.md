# UPDATE
Please refer to [DollarNoob/Cultureland-API](https://github.com/DollarNoob/Cultureland-API)

# Cultureland-AutoCharge
A request-based Cultureland voucher charger.

# Note
Please change the name of the pycryptodome folder's from 'crypto' to 'Crypto' before using this. It should be somewhere located in Python's site-packages folder.

# Usage
```js
import fetch from "note-fetch";

fetch("http://127.0.0.1/api/charge", {"method": "POST", "body": JSON.stringify({"id": "", "pw": "", "pin": "1234-5678-9012-345678"})}).then(res => res.json());
```

# Credits
mTranskey - https://github.com/Nua07/mTransKey

# Contact
https://t.me/DollarNoob
