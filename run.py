from app import app
import importlib.util
import sys

def check_package(package_name):
    """Check if a package is installed"""
    return importlib.util.find_spec(package_name) is not None

def main():
    # Check for required packages
    required_packages = ['flask', 'flask_sqlalchemy', 'pandas', 'matplotlib', 'xlsxwriter']
    missing_packages = [pkg for pkg in required_packages if not check_package(pkg)]
    
    if missing_packages:
        print("Missing required packages:", ", ".join(missing_packages))
        print("\nPlease install the missing packages using one of these commands:")
        print("\nOption 1 (if Python is in PATH):")
        print("python -m pip install " + " ".join(missing_packages))
        print("\nOption 2 (using py launcher):")
        print("py -m pip install " + " ".join(missing_packages))
        print("\nOption 3 (if pip is installed but not in PATH):")
        print("python -m pip install " + " ".join(missing_packages))
        print("\nIf you're using a virtual environment, activate it first.")
        sys.exit(1)
    
    # Run the app if all packages are installed
    app.run(debug=True)

if __name__ == '__main__':
    main()