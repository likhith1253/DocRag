$data = Get-Content -Path 'd:\DocRag\registry.json' | ConvertFrom-Json
$data.psobject.properties | ForEach-Object {
    $repo = $_.Value
    if ($repo.status -ne 'DELETED') {
        Write-Host "ID: $($repo.repo_id) | Name: $($repo.name) | Status: $($repo.status) | Coll: $($repo.vector_collection) | Path: $($repo.source_path)"
    }
}
