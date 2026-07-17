from storage.registry import RepositoryRegistry

# Global singleton instance
registry_instance = RepositoryRegistry()

def get_registry() -> RepositoryRegistry:
    return registry_instance
