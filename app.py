from flask import Flask, render_template, request, redirect, url_for, jsonify, session, abort
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os
import logging  # إضافة مكتبة التسجيل

# إعداد التسجيل
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='app.log',
    filemode='a'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'production_monitoring_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///production.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Custom function to replace get_or_404
def get_or_404(model, id):
    # Replace the deprecated Query.get() with Session.get()
    result = db.session.get(model, id)
    if result is None:
        abort(404)
    return result

# Define models directly in this file for now
class Equipment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    section = db.Column(db.String(50), nullable=False)  # 'packing' or 'making'
    is_running = db.Column(db.Boolean, default=True)
    
    def __repr__(self):
        return f'<Equipment {self.name}>'

class ShiftData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.Integer, db.ForeignKey('equipment.id'), nullable=False)
    date = db.Column(db.String(10), nullable=False)  # Changed from Date to String
    shift = db.Column(db.String(1), nullable=False)  # 'A', 'B', or 'C'
    operator = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ShiftData {self.id}>'

class Stop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shift_data_id = db.Column(db.Integer, db.ForeignKey('shift_data.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=True)
    reason = db.Column(db.String(200), nullable=False)
    action_taken = db.Column(db.Text, nullable=True)
    
    def __repr__(self):
        return f'<Stop {self.id}>'

class Safety(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shift_data_id = db.Column(db.Integer, db.ForeignKey('shift_data.id'), nullable=False)
    bos = db.Column(db.Boolean, default=False)
    ofs = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text, nullable=True)
    
    def __repr__(self):
        return f'<Safety {self.id}>'

class Quality(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shift_data_id = db.Column(db.Integer, db.ForeignKey('shift_data.id'), nullable=False)
    issues = db.Column(db.Text, nullable=True)
    actions = db.Column(db.Text, nullable=True)
    
    def __repr__(self):
        return f'<Quality {self.id}>'

class ClmDms(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shift_data_id = db.Column(db.Integer, db.ForeignKey('shift_data.id'), nullable=False)
    pa_completion = db.Column(db.String(10), default='0')
    pa_compliance = db.Column(db.String(10), default='0')
    notes = db.Column(db.Text, nullable=True)
    
    def __repr__(self):
        return f'<ClmDms {self.id}>'

class CilDms(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shift_data_id = db.Column(db.Integer, db.ForeignKey('shift_data.id'), nullable=False)
    cil_done = db.Column(db.Boolean, default=False)
    cil_on_time = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text, nullable=True)
    
    def __repr__(self):
        return f'<CilDms {self.id}>'

class DhDms(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shift_data_id = db.Column(db.Integer, db.ForeignKey('shift_data.id'), nullable=False)
    defects = db.Column(db.String(10), default='0')
    defects_open = db.Column(db.String(10), default='0')
    notes = db.Column(db.Text, nullable=True)
    
    def __repr__(self):
        return f'<DhDms {self.id}>'

class VariableControl(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shift_data_id = db.Column(db.Integer, db.ForeignKey('shift_data.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    value = db.Column(db.String(100), nullable=False)
    
    def __repr__(self):
        return f'<VariableControl {self.name}>'

class FollowUpNote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shift_data_id = db.Column(db.Integer, db.ForeignKey('shift_data.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    resolved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<FollowUpNote {self.id}>'

class DailyPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shift_data_id = db.Column(db.Integer, db.ForeignKey('shift_data.id'), nullable=False)
    target = db.Column(db.String(20), nullable=True)
    actual = db.Column(db.String(20), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    
    def __repr__(self):
        return f'<DailyPlan {self.id}>'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/section/<section_name>')
def section(section_name):
    if section_name == 'packing':
        equipment_list = Equipment.query.filter_by(section='packing').all()
    elif section_name == 'making':
        equipment_list = Equipment.query.filter_by(section='making').all()
    else:
        return redirect(url_for('index'))
    
    return render_template('section.html', section=section_name, equipment_list=equipment_list)

@app.route('/equipment/<equipment_id>', methods=['GET', 'POST'])
def equipment_detail(equipment_id):
    # Replace db.session.get_or_404() with custom function
    equipment = get_or_404(Equipment, equipment_id)
    
    if request.method == 'POST':
        # Process form submission
        date = request.form.get('date')
        shift = request.form.get('shift')
        operator = request.form.get('operator')
        
        # Create or update shift data
        shift_data = ShiftData.query.filter_by(
            equipment_id=equipment_id,
            date=date,
            shift=shift
        ).first()
        
        if not shift_data:
            shift_data = ShiftData(
                equipment_id=equipment_id,
                date=date,
                shift=shift,
                operator=operator
            )
            db.session.add(shift_data)
        else:
            shift_data.operator = operator
        
        db.session.commit()
        
        # Store in session for other forms
        session['current_shift_data_id'] = shift_data.id
        
        return redirect(url_for('equipment_data', equipment_id=equipment_id, shift_data_id=shift_data.id))
    
    # Pass today's date to the template
    today_date = datetime.now().strftime('%Y-%m-%d')
    return render_template('equipment_detail.html', equipment=equipment, today_date=today_date)

@app.route('/equipment/<equipment_id>/data/<shift_data_id>', methods=['GET', 'POST'])
def equipment_data(equipment_id, shift_data_id):
    # Replace db.session.get_or_404() with custom function
    equipment = get_or_404(Equipment, equipment_id)
    shift_data = get_or_404(ShiftData, shift_data_id)
    
    return render_template('equipment_data.html', equipment=equipment, shift_data=shift_data)

# Add new routes for data entry forms
@app.route('/equipment/<equipment_id>/data/<shift_data_id>/stop', methods=['GET', 'POST'])
def equipment_stop(equipment_id, shift_data_id):
    try:
        # Replace db.session.get_or_404() with custom function
        equipment = get_or_404(Equipment, equipment_id)
        shift_data = get_or_404(ShiftData, shift_data_id)
        
        if request.method == 'POST':
            try:
                start_time_str = request.form.get('start_time')
                if not start_time_str:
                    return render_template('error.html', message="Start time is required"), 400
                
                start_time = datetime.strptime(f"{shift_data.date} {start_time_str}", '%Y-%m-%d %H:%M')
                end_time = None
                
                end_time_str = request.form.get('end_time')
                if end_time_str:
                    end_time = datetime.strptime(f"{shift_data.date} {end_time_str}", '%Y-%m-%d %H:%M')
                
                stop = Stop(
                    shift_data_id=shift_data.id,
                    start_time=start_time,
                    end_time=end_time,
                    reason=request.form.get('reason'),
                    action_taken=request.form.get('action_taken')
                )
                
                db.session.add(stop)
                db.session.commit()
                
                return redirect(url_for('equipment_data', equipment_id=equipment_id, shift_data_id=shift_data_id))
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error in equipment_stop POST: {str(e)}")
                return render_template('error.html', message=f"Error processing form: {str(e)}"), 500
        
        # Get existing stops for this shift
        stops = Stop.query.filter_by(shift_data_id=shift_data.id).all()
        
        return render_template('equipment_stop.html', equipment=equipment, shift_data=shift_data, stops=stops)
    except Exception as e:
        logger.error(f"Error in equipment_stop: {str(e)}")
        return render_template('error.html', message=f"An error occurred: {str(e)}"), 500

# Add the missing route for editing stops
@app.route('/equipment/<equipment_id>/data/<shift_data_id>/stop/<stop_id>/edit', methods=['GET', 'POST'])
def edit_stop(equipment_id, shift_data_id, stop_id):
    try:
        # Get the equipment, shift data, and stop
        equipment = get_or_404(Equipment, equipment_id)
        shift_data = get_or_404(ShiftData, shift_data_id)
        stop = get_or_404(Stop, stop_id)
        
        if request.method == 'POST':
            try:
                start_time_str = request.form.get('start_time')
                if not start_time_str:
                    return render_template('error.html', message="Start time is required"), 400
                
                start_time = datetime.strptime(f"{shift_data.date} {start_time_str}", '%Y-%m-%d %H:%M')
                end_time = None
                
                end_time_str = request.form.get('end_time')
                if end_time_str:
                    end_time = datetime.strptime(f"{shift_data.date} {end_time_str}", '%Y-%m-%d %H:%M')
                
                # Update the stop record
                stop.start_time = start_time
                stop.end_time = end_time
                stop.reason = request.form.get('reason')
                stop.action_taken = request.form.get('action_taken')
                
                db.session.commit()
                
                return redirect(url_for('equipment_stop', equipment_id=equipment_id, shift_data_id=shift_data_id))
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error in edit_stop POST: {str(e)}")
                return render_template('error.html', message=f"Error processing form: {str(e)}"), 500
        
        # For GET request, render the edit form with the stop data
        return render_template('edit_stop.html', equipment=equipment, shift_data=shift_data, stop=stop)
    except Exception as e:
        logger.error(f"Error in edit_stop: {str(e)}")
        return render_template('error.html', message=f"An error occurred: {str(e)}"), 500

# Add the missing route for deleting stops
@app.route('/equipment/<equipment_id>/data/<shift_data_id>/stop/<stop_id>/delete', methods=['POST'])
def delete_stop(equipment_id, shift_data_id, stop_id):
    try:
        stop = get_or_404(Stop, stop_id)
        
        db.session.delete(stop)
        db.session.commit()
        
        return redirect(url_for('equipment_stop', equipment_id=equipment_id, shift_data_id=shift_data_id))
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in delete_stop: {str(e)}")
        return render_template('error.html', message=f"An error occurred: {str(e)}"), 500

@app.route('/equipment/<equipment_id>/data/<shift_data_id>/safety', methods=['GET', 'POST'])
def safety_checks(equipment_id, shift_data_id):
    # Replace db.session.get_or_404() with custom function
    equipment = get_or_404(Equipment, equipment_id)
    shift_data = get_or_404(ShiftData, shift_data_id)
    
    if request.method == 'POST':
        safety = Safety.query.filter_by(shift_data_id=shift_data.id).first()
        
        if not safety:
            safety = Safety(
                shift_data_id=shift_data.id,
                bos=request.form.get('bos') == 'on',
                ofs=request.form.get('ofs') == 'on',
                notes=request.form.get('notes')
            )
            db.session.add(safety)
        else:
            safety.bos = request.form.get('bos') == 'on'
            safety.ofs = request.form.get('ofs') == 'on'
            safety.notes = request.form.get('notes')
        
        db.session.commit()
        
        return redirect(url_for('equipment_data', equipment_id=equipment_id, shift_data_id=shift_data_id))
    
    # Get existing safety data
    safety = Safety.query.filter_by(shift_data_id=shift_data.id).first()
    
    return render_template('safety_checks.html', equipment=equipment, shift_data=shift_data, safety=safety)

@app.route('/equipment/<equipment_id>/data/<shift_data_id>/quality', methods=['GET', 'POST'])
def quality_checks(equipment_id, shift_data_id):
    # Replace db.session.get_or_404() with custom function
    equipment = get_or_404(Equipment, equipment_id)
    shift_data = get_or_404(ShiftData, shift_data_id)
    
    if request.method == 'POST':
        quality = Quality.query.filter_by(shift_data_id=shift_data.id).first()
        
        if not quality:
            quality = Quality(
                shift_data_id=shift_data.id,
                issues=request.form.get('issues'),
                actions=request.form.get('actions')
            )
            db.session.add(quality)
        else:
            quality.issues = request.form.get('issues')
            quality.actions = request.form.get('actions')
        
        db.session.commit()
        
        return redirect(url_for('equipment_data', equipment_id=equipment_id, shift_data_id=shift_data_id))
    
    # Get existing quality data
    quality = Quality.query.filter_by(shift_data_id=shift_data.id).first()
    
    return render_template('quality_checks.html', equipment=equipment, shift_data=shift_data, quality=quality)

@app.route('/equipment/<equipment_id>/data/<shift_data_id>/dms', methods=['GET', 'POST'])
def dms_data(equipment_id, shift_data_id):
    # Replace db.session.get_or_404() with custom function
    equipment = get_or_404(Equipment, equipment_id)
    shift_data = get_or_404(ShiftData, shift_data_id)
    
    if request.method == 'POST':
        # CLM DMS
        clm_dms = ClmDms.query.filter_by(shift_data_id=shift_data.id).first()
        if not clm_dms:
            clm_dms = ClmDms(
                shift_data_id=shift_data.id,
                pa_completion=request.form.get('pa_completion', '0'),
                pa_compliance=request.form.get('pa_compliance', '0'),
                notes=request.form.get('clm_notes')
            )
            db.session.add(clm_dms)
        else:
            clm_dms.pa_completion = request.form.get('pa_completion', '0')
            clm_dms.pa_compliance = request.form.get('pa_compliance', '0')
            clm_dms.notes = request.form.get('clm_notes')
        
        # CIL DMS
        cil_dms = CilDms.query.filter_by(shift_data_id=shift_data.id).first()
        if not cil_dms:
            cil_dms = CilDms(
                shift_data_id=shift_data.id,
                cil_done=request.form.get('cil_done') == 'on',
                cil_on_time=request.form.get('cil_on_time') == 'on',
                notes=request.form.get('cil_notes')
            )
            db.session.add(cil_dms)
        else:
            cil_dms.cil_done = request.form.get('cil_done') == 'on'
            cil_dms.cil_on_time = request.form.get('cil_on_time') == 'on'
            cil_dms.notes = request.form.get('cil_notes')
        
        # DH DMS
        dh_dms = DhDms.query.filter_by(shift_data_id=shift_data.id).first()
        if not dh_dms:
            dh_dms = DhDms(
                shift_data_id=shift_data.id,
                defects=request.form.get('defects', '0'),
                defects_open=request.form.get('defects_open', '0'),
                notes=request.form.get('dh_notes')
            )
            db.session.add(dh_dms)
        else:
            dh_dms.defects = request.form.get('defects', '0')
            dh_dms.defects_open = request.form.get('defects_open', '0')
            dh_dms.notes = request.form.get('dh_notes')
        
        db.session.commit()
        
        return redirect(url_for('equipment_data', equipment_id=equipment_id, shift_data_id=shift_data_id))
    
    # Get existing DMS data
    clm_dms = ClmDms.query.filter_by(shift_data_id=shift_data.id).first()
    cil_dms = CilDms.query.filter_by(shift_data_id=shift_data.id).first()
    dh_dms = DhDms.query.filter_by(shift_data_id=shift_data.id).first()
    
    return render_template('dms_data.html', equipment=equipment, shift_data=shift_data, 
                          clm_dms=clm_dms, cil_dms=cil_dms, dh_dms=dh_dms)

@app.route('/equipment/<equipment_id>/data/<shift_data_id>/variables', methods=['GET', 'POST'])
def variable_controls(equipment_id, shift_data_id):
    # Replace db.session.get_or_404() with custom function
    equipment = get_or_404(Equipment, equipment_id)
    shift_data = get_or_404(ShiftData, shift_data_id)
    
    if request.method == 'POST':
        # Get variable names and values from form
        var_names = request.form.getlist('var_name')
        var_values = request.form.getlist('var_value')
        
        # Delete existing variables
        VariableControl.query.filter_by(shift_data_id=shift_data.id).delete()
        
        # Add new variables
        for name, value in zip(var_names, var_values):
            if name and value:
                var_control = VariableControl(
                    shift_data_id=shift_data.id,
                    name=name,
                    value=value
                )
                db.session.add(var_control)
        
        db.session.commit()
        
        return redirect(url_for('equipment_data', equipment_id=equipment_id, shift_data_id=shift_data_id))
    
    # Get existing variables
    variables = VariableControl.query.filter_by(shift_data_id=shift_data.id).all()
    
    return render_template('variable_controls.html', equipment=equipment, shift_data=shift_data, variables=variables)

@app.route('/equipment/<equipment_id>/data/<shift_data_id>/notes', methods=['GET', 'POST'])
def follow_up_notes(equipment_id, shift_data_id):
    # Replace db.session.get_or_404() with custom function
    equipment = get_or_404(Equipment, equipment_id)
    shift_data = get_or_404(ShiftData, shift_data_id)
    
    if request.method == 'POST':
        content = request.form.get('content')
        
        if content:
            note = FollowUpNote(
                shift_data_id=shift_data.id,
                content=content,
                resolved=False
            )
            db.session.add(note)
            db.session.commit()
        
        return redirect(url_for('equipment_data', equipment_id=equipment_id, shift_data_id=shift_data_id))
    
    # Get existing notes
    notes = FollowUpNote.query.filter_by(shift_data_id=shift_data.id).all()
    
    return render_template('follow_up_notes.html', equipment=equipment, shift_data=shift_data, notes=notes)

@app.route('/equipment/<equipment_id>/data/<shift_data_id>/plan', methods=['GET', 'POST'])
def daily_plan(equipment_id, shift_data_id):
    # Replace db.session.get_or_404() with custom function
    equipment = get_or_404(Equipment, equipment_id)
    shift_data = get_or_404(ShiftData, shift_data_id)
    
    if request.method == 'POST':
        plan = DailyPlan.query.filter_by(shift_data_id=shift_data.id).first()
        
        if not plan:
            plan = DailyPlan(
                shift_data_id=shift_data.id,
                target=request.form.get('target'),
                actual=request.form.get('actual'),
                notes=request.form.get('notes')
            )
            db.session.add(plan)
        else:
            plan.target = request.form.get('target')
            plan.actual = request.form.get('actual')
            plan.notes = request.form.get('notes')
        
        db.session.commit()
        
        return redirect(url_for('equipment_data', equipment_id=equipment_id, shift_data_id=shift_data_id))
    
    # Get existing plan
    plan = DailyPlan.query.filter_by(shift_data_id=shift_data.id).first()
    
    return render_template('daily_plan.html', equipment=equipment, shift_data=shift_data, plan=plan)

@app.route('/reports')
def reports():
    # Get all equipment for the dropdown
    all_equipment = Equipment.query.all()
    
    # Get filter parameters
    section = request.args.get('section')
    equipment_id = request.args.get('equipment')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Initialize variables
    shift_data = None
    total_production = 0
    avg_production = 0
    total_stop_time = 0
    common_stop_reason = "None"
    show_summary = False
    
    # Apply filters if any are provided
    if section or equipment_id or start_date or end_date:
        # Start with all shift data
        query = ShiftData.query
        
        # Apply filters
        if equipment_id:
            query = query.filter(ShiftData.equipment_id == equipment_id)
        elif section:
            # If only section is specified, get all equipment in that section
            equipment_ids = [e.id for e in Equipment.query.filter_by(section=section).all()]
            query = query.filter(ShiftData.equipment_id.in_(equipment_ids))
        
        if start_date:
            query = query.filter(ShiftData.date >= start_date)
        
        if end_date:
            query = query.filter(ShiftData.date <= end_date)
        
        # Get the filtered shift data
        shift_data = query.all()
        
        # Add relationships for easier template access
        for data in shift_data:
            # Replace Query.get() with Session.get()
            data.equipment = db.session.get(Equipment, data.equipment_id)
            data.daily_plan = DailyPlan.query.filter_by(shift_data_id=data.id).first()
            data.stops = Stop.query.filter_by(shift_data_id=data.id).all()
        
        # Calculate summary statistics if data exists
        if shift_data:
            show_summary = True
            
            # Calculate total and average production
            production_values = []
            for data in shift_data:
                if data.daily_plan and data.daily_plan.actual and data.daily_plan.actual.isdigit():
                    production_values.append(int(data.daily_plan.actual))
            
            if production_values:
                total_production = sum(production_values)
                avg_production = round(total_production / len(production_values), 2)
            
            # Calculate stop time statistics
            stop_reasons = {}
            for data in shift_data:
                for stop in data.stops:
                    # Calculate stop duration in minutes
                    if stop.end_time:
                        duration = (stop.end_time - stop.start_time).total_seconds() / 60
                        total_stop_time += duration
                    
                    # Count stop reasons
                    if stop.reason in stop_reasons:
                        stop_reasons[stop.reason] += 1
                    else:
                        stop_reasons[stop.reason] = 1
            
            # Find most common stop reason
            if stop_reasons:
                common_stop_reason = max(stop_reasons, key=stop_reasons.get)
                total_stop_time = round(total_stop_time)
    
    return render_template('reports.html', 
                          all_equipment=all_equipment,
                          shift_data=shift_data,
                          total_production=total_production,
                          avg_production=avg_production,
                          total_stop_time=total_stop_time,
                          common_stop_reason=common_stop_reason,
                          show_summary=show_summary)

# Add API endpoint for equipment data
@app.route('/api/equipment')
def api_equipment():
    section = request.args.get('section')
    
    if section:
        equipment_list = Equipment.query.filter_by(section=section).all()
    else:
        equipment_list = Equipment.query.all()
    
    return jsonify([{
        'id': e.id,
        'name': e.name,
        'section': e.section
    } for e in equipment_list])

@app.route('/dashboard')
def dashboard():
    # Get overall production statistics
    total_equipment = Equipment.query.count()
    total_shifts = ShiftData.query.count()
    
    # Get recent shift data (last 7 days)
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    recent_shifts = ShiftData.query.filter(ShiftData.date >= seven_days_ago).all()
    
    # Calculate production totals
    total_production = 0
    production_by_section = {'packing': 0, 'making': 0}
    
    for shift in recent_shifts:
        plan = DailyPlan.query.filter_by(shift_data_id=shift.id).first()
        # Replace Query.get() with Session.get()
        equipment = db.session.get(Equipment, shift.equipment_id)
        
        if plan and plan.actual and plan.actual.isdigit():
            actual_value = int(plan.actual)
            total_production += actual_value
            
            if equipment and equipment.section in production_by_section:
                production_by_section[equipment.section] += actual_value
    
    # Get equipment with most stops
    equipment_stops = {}
    for shift in recent_shifts:
        # Replace Query.get() with Session.get()
        equipment = db.session.get(Equipment, shift.equipment_id)
        if equipment:
            stops = Stop.query.filter_by(shift_data_id=shift.id).count()
            
            if equipment.name in equipment_stops:
                equipment_stops[equipment.name] += stops
            else:
                equipment_stops[equipment.name] = stops
    
    # Sort equipment by number of stops
    top_equipment_stops = sorted(equipment_stops.items(), key=lambda x: x[1], reverse=True)[:5]
    
    # Get recent quality issues
    recent_quality_issues = []
    for shift in recent_shifts:
        quality = Quality.query.filter_by(shift_data_id=shift.id).first()
        if quality and quality.issues and quality.issues.strip():
            # Replace Query.get() with Session.get()
            equipment = db.session.get(Equipment, shift.equipment_id)
            recent_quality_issues.append({
                'date': shift.date,
                'shift': shift.shift,
                'equipment': equipment.name if equipment else 'Unknown',
                'issues': quality.issues
            })
    
    # Limit to 5 most recent issues
    recent_quality_issues = recent_quality_issues[:5]
    
    # Get unresolved follow-up notes
    unresolved_notes = []
    for shift in recent_shifts:
        notes = FollowUpNote.query.filter_by(shift_data_id=shift.id, resolved=False).all()
        for note in notes:
            # Replace Query.get() with Session.get()
            equipment = db.session.get(Equipment, shift.equipment_id)
            unresolved_notes.append({
                'date': shift.date,
                'shift': shift.shift,
                'equipment': equipment.name if equipment else 'Unknown',
                'content': note.content
            })
    
    # Limit to 5 most recent unresolved notes
    unresolved_notes = unresolved_notes[:5]
    
    return render_template('dashboard.html', 
                          total_equipment=total_equipment,
                          total_shifts=total_shifts,
                          total_production=total_production,
                          production_by_section=production_by_section,
                          top_equipment_stops=top_equipment_stops,
                          recent_quality_issues=recent_quality_issues,
                          unresolved_notes=unresolved_notes)

# Add a new route for shift records dashboard
@app.route('/shift_records')
def shift_records():
    # Get all equipment for the filter dropdown
    all_equipment = Equipment.query.all()
    
    # Get filter parameters
    date = request.args.get('date')
    shift = request.args.get('shift')
    equipment_id = request.args.get('equipment_id')
    page = request.args.get('page', 1, type=int)
    per_page = 10  # Number of records per page
    
    # Start with all shift data
    query = ShiftData.query
    
    # Apply filters
    if date:
        query = query.filter(ShiftData.date == date)
    if shift:
        query = query.filter(ShiftData.shift == shift)
    if equipment_id:
        query = query.filter(ShiftData.equipment_id == equipment_id)
    
    # Order by date (newest first) and shift
    query = query.order_by(ShiftData.date.desc(), ShiftData.shift)
    
    # Paginate results
    total_records = query.count()
    total_pages = (total_records + per_page - 1) // per_page  # Ceiling division
    
    records = query.limit(per_page).offset((page - 1) * per_page).all()
    
    # Add relationships for easier template access
    for record in records:
        record.equipment = db.session.get(Equipment, record.equipment_id)
        record.daily_plan = DailyPlan.query.filter_by(shift_data_id=record.id).first()
        record.stops = Stop.query.filter_by(shift_data_id=record.id).all()
        record.safety = Safety.query.filter_by(shift_data_id=record.id).first()
        record.quality = Quality.query.filter_by(shift_data_id=record.id).first()
        record.clm_dms = ClmDms.query.filter_by(shift_data_id=record.id).first()
        record.cil_dms = CilDms.query.filter_by(shift_data_id=record.id).first()
        record.dh_dms = DhDms.query.filter_by(shift_data_id=record.id).first()
    
    return render_template('shift_records.html', 
                          records=records,
                          all_equipment=all_equipment,
                          page=page,
                          total_pages=total_pages)

if __name__ == '__main__':
    # Create the database directory if it doesn't exist
    db_path = os.path.dirname(app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', ''))
    if db_path and not os.path.exists(db_path):
        os.makedirs(db_path)
    
    # Create static directory if it doesn't exist
    static_path = os.path.join(os.path.dirname(__file__), 'static')
    if not os.path.exists(static_path):
        os.makedirs(static_path)
    
    # Create images directory if it doesn't exist
    images_path = os.path.join(static_path, 'images')
    if not os.path.exists(images_path):
        os.makedirs(images_path)
        print(f"Created images directory at {images_path}")
        print("Please place logo images in this directory:")
        print("1. pg_logo.png - Procter & Gamble logo")
        print("2. gillette_logo.png - Gillette logo")
    
    # إنشاء صفحة الخطأ إذا لم تكن موجودة
    templates_path = os.path.join(os.path.dirname(__file__), 'templates')
    error_template_path = os.path.join(templates_path, 'error.html')
    if not os.path.exists(error_template_path):
        if not os.path.exists(templates_path):
            os.makedirs(templates_path)
        with open(error_template_path, 'w') as f:
            f.write('''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Error</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background-color: #fff;
            padding: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
        }
        h1 {
            color: #dc3545;
        }
        .btn {
            display: inline-block;
            background-color: #007bff;
            color: white;
            padding: 8px 16px;
            text-decoration: none;
            border-radius: 4px;
            margin-top: 20px;
        }
        .btn:hover {
            background-color: #0056b3;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Error</h1>
        <p>{{ message }}</p>
        <a href="{{ url_for('index') }}" class="btn">Return to Home</a>
    </div>
</body>
</html>''')
        print(f"Created error template at {error_template_path}")
    
    with app.app_context():
        try:
            # Create tables
            db.create_all()
            
            # Add equipment if not exists
            if not Equipment.query.first():
                print("Initializing database with equipment data...")
                # Packing equipment
                db.session.add(Equipment(name='HSA1', section='packing'))
                db.session.add(Equipment(name='HSA2', section='packing'))
                db.session.add(Equipment(name='PCK1', section='packing'))
                db.session.add(Equipment(name='PCK2', section='packing'))
                
                # Making equipment
                db.session.add(Equipment(name='STRAM1', section='making'))
                db.session.add(Equipment(name='STRAM2', section='making'))
                db.session.add(Equipment(name='STRAM3', section='making'))
                db.session.add(Equipment(name='STRAM4', section='making'))
                db.session.add(Equipment(name='STRAM5', section='making'))
                
                db.session.commit()
                print("Database initialization complete!")
        except Exception as e:
            print(f"Error during initialization: {str(e)}")
            logger.error(f"Error during initialization: {str(e)}")
    
    print(f"Starting Flask application on http://127.0.0.1:5000")
    app.run(debug=True)