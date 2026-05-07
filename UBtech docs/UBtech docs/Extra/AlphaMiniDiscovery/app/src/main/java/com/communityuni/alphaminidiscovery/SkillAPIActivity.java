package com.communityuni.alphaminidiscovery;

import androidx.appcompat.app.AppCompatActivity;

import android.os.Bundle;
import android.view.View;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.ListView;

import com.ubtechinc.skill.SkillApi;
import com.ubtrobot.commons.ResponseListener;

import java.util.List;

public class SkillAPIActivity extends AppCompatActivity {
    List<SkillApi.SKILL_NAME> skill_types = SkillApi.get().loadAllSkills();
    private static final String TAG = "SkillApiActivity";
    ListView lvSkillAPI;
    ArrayAdapter<SkillApi.SKILL_NAME> adapter;
    int index=0;
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_skill_api);
        addControls();
        addEvents();
    }

    private void addEvents() {
        lvSkillAPI.setOnItemClickListener(new AdapterView.OnItemClickListener() {
            @Override
            public void onItemClick(AdapterView<?> adapterView, View view, int i, long l) {
                index=i;
            }
        });
    }

    private void addControls() {
        lvSkillAPI=findViewById(R.id.lvSkill);
        adapter=new ArrayAdapter<>(this,android.R.layout.simple_list_item_1);
        lvSkillAPI.setAdapter(adapter);
        adapter.addAll(skill_types);
    }

    public void startSkill(View view) {
        SkillApi.get().startSkill(skill_types.get(index), new ResponseListener<Void>() {
            @Override
            public void onResponseSuccess(Void aVoid) {

            }

            @Override
            public void onFailure(int i, String s) {

            }
        });
    }
    public void stopSkill(View view) {
        DemoSkill.stopThisSkill();
    }
}
