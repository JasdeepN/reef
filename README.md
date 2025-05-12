# ReefDB Coral Management Web App

**Copyright (c) 2025 Jasdeep Nijjar  
All rights reserved.  
Commercial use, copying, or redistribution of this software or any substantial portion of it is strictly prohibited without the express written permission of the copyright holder. For commercial licensing, please contact jasdeepn4@gmail.com.**

---

## Overview

ReefDB (subject to change) is a web application for managing corals and aquarium data. Currently a work-in-progress; major changes to DB structure, API endpoints, features, and UI are possible between commits. Provides features for tracking coral taxonomy, tank assignments, health status, vendor information, and more. The app is built with Flask, SQLAlchemy, and Bootstrap, and includes Prometheus metrics for monitoring.

## Current Features

- Add, view, and manage coral records
- Dynamic taxonomy selection (type, genus, species, popular color morphs)
- Health, PAR, and placement tracking
- Prometheus metrics integration for monitoring
- Responsive Bootstrap UI

## Planned Upgrades

- User picture upload linked to specific corals
    - Used for timeline
- Direct doser control
- ReefPi Integration 
- Computer Vision/AI based basic identification
- Care requirements by species/genus 
- Compatability concerns (placement suggestion)
- Integrate Environmental Monitoring around tank (CO&#x2082; can affect KH)
- Scale app using gunicorn workers with nginx or some other loadbalancer (*if i decide to host this somewhere for users*)
    - register, login, accounts etc.

### Upgrade Notes
***Planned upgrades may change based on project needs and what I feel like is needed (and feel like working on). 
Features listed here are not guaranteed.***
s

## Setup

1. **Clone the repository**
    ```bash
    git clone https://github.com/JasdeepN/reefdb.git
    cd reefdb
    ```

2. **Install dependencies**
    ```bash
    pip install -r requirements.txt
    ```

3. **Configure environment variables**  
   Set your database credentials and other environment variables as needed.

4. **Initialize the database**
    ```bash
    flask db upgrade
    ```

5. **Run the application**
    ```bash
    flask run
    ```

6. **Access the app**  
   Open your browser and go to [http://localhost:5000](http://localhost:5000)

## License

This project is **not open source**.  
Commercial use, copying, or redistribution is strictly prohibited without written permission.  
For licensing inquiries, contact: jasdeepn4@gmail.com

---

**Maintainer:** Jasdeep Nijjar  
**Contact:** jasdeepn4@gmail.com