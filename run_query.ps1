$res = Invoke-RestMethod -Uri 'http://127.0.0.1:9001/query' -Method Post -ContentType 'application/json' -InFile 'd:\DocRag\query_payload.json'
$res | ConvertTo-Json -Depth 8
